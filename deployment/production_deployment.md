# Production Deployment Guide for SNMP Network Monitoring

## 🚀 Production Deployment Configuration

### Prerequisites

#### System Requirements
- **OS**: Ubuntu 20.04+ / CentOS 8+ / RHEL 8+
- **RAM**: 8GB minimum, 16GB recommended
- **CPU**: 4 cores minimum, 8 cores recommended  
- **Storage**: 100GB minimum, SSD recommended
- **Network**: High bandwidth connection for SNMP polling

#### Software Requirements
- Python 3.9+
- PostgreSQL 13+
- Redis 6.0+
- Nginx 1.18+
- Supervisor or systemd

### Installation Steps

#### 1. System Setup
```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y python3.9 python3.9-venv python3-pip postgresql-13 \
    redis-server nginx supervisor git build-essential libpq-dev \
    libsnmp-dev snmp snmp-mibs-downloader

# Create application user
sudo useradd -m -s /bin/bash snmpmon
sudo usermod -aG sudo snmpmon
```

#### 2. Database Setup
```sql
-- PostgreSQL setup
sudo -u postgres psql

CREATE DATABASE snmp_monitoring;
CREATE USER snmpmon WITH ENCRYPTED PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE snmp_monitoring TO snmpmon;
ALTER USER snmpmon CREATEDB;

-- Tune PostgreSQL for production
-- Edit /etc/postgresql/13/main/postgresql.conf
shared_preload_libraries = 'pg_stat_statements'
max_connections = 200
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB
maintenance_work_mem = 64MB
```

#### 3. Application Deployment
```bash
# Switch to application user
sudo su - snmpmon

# Clone repository
git clone <repository-url> /home/snmpmon/snmp-monitoring
cd /home/snmpmon/snmp-monitoring

# Create virtual environment
python3.9 -m venv venv
source venv/bin/activate

# Install production requirements
pip install -r requirements-production.txt

# Configure environment
cp .env.example .env
# Edit .env with production values
```

#### 4. Environment Configuration
```bash
# /home/snmpmon/snmp-monitoring/.env
SECRET_KEY=your-very-secure-secret-key-here
DEBUG=False
ALLOWED_HOSTS=your-domain.com,10.0.0.100

# Database
DB_NAME=snmp_monitoring
DB_USER=snmpmon
DB_PASSWORD=your_secure_password
DB_HOST=localhost
DB_PORT=5432

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Email (for alerts)
EMAIL_HOST=smtp.company.com
EMAIL_PORT=587
EMAIL_HOST_USER=snmp-alerts@company.com
EMAIL_HOST_PASSWORD=email_password
DEFAULT_FROM_EMAIL=snmp-alerts@company.com

# Alert recipients
ALERT_EMAIL_RECIPIENTS=admin@company.com,netops@company.com

# Security
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

#### 5. Django Setup
```bash
# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput

# Test configuration
python manage.py check --deploy
```

#### 6. MIB Files Setup
```bash
# Create MIB directories
mkdir -p /home/snmpmon/snmp-monitoring/mibs/{cisco,huawei,h3c,juniper,standard}

# Download and install vendor MIBs
# Place vendor MIB files in respective directories:
# - mibs/cisco/ - Cisco MIB files
# - mibs/huawei/ - Huawei MIB files  
# - mibs/h3c/ - H3C MIB files
# - mibs/standard/ - Standard IETF MIBs

# Set proper permissions
chmod -R 755 /home/snmpmon/snmp-monitoring/mibs/
```

### Service Configuration

#### 7. Gunicorn Configuration
```python
# /home/snmpmon/snmp-monitoring/gunicorn.conf.py
bind = "127.0.0.1:8000"
workers = 4
worker_class = "gevent"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 30
keepalive = 2
preload_app = True
```

#### 8. Systemd Services
```ini
# /etc/systemd/system/snmpmon-web.service
[Unit]
Description=SNMP Monitoring Web Application
After=network.target postgresql.service redis.service

[Service]
User=snmpmon
Group=snmpmon
WorkingDirectory=/home/snmpmon/snmp-monitoring
Environment=DJANGO_SETTINGS_MODULE=config.settings.production
ExecStart=/home/snmpmon/snmp-monitoring/venv/bin/gunicorn -c gunicorn.conf.py config.wsgi:application
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/snmpmon-worker.service
[Unit]
Description=SNMP Monitoring Celery Worker
After=network.target postgresql.service redis.service

[Service]
User=snmpmon
Group=snmpmon
WorkingDirectory=/home/snmpmon/snmp-monitoring
Environment=DJANGO_SETTINGS_MODULE=config.settings.production
ExecStart=/home/snmpmon/snmp-monitoring/venv/bin/celery -A config worker -l info -c 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/snmpmon-beat.service
[Unit]
Description=SNMP Monitoring Celery Beat Scheduler
After=network.target postgresql.service redis.service

[Service]
User=snmpmon
Group=snmpmon
WorkingDirectory=/home/snmpmon/snmp-monitoring
Environment=DJANGO_SETTINGS_MODULE=config.settings.production
ExecStart=/home/snmpmon/snmp-monitoring/venv/bin/celery -A config beat -l info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 9. Nginx Configuration
```nginx
# /etc/nginx/sites-available/snmpmon
upstream snmpmon_app {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    # SSL configuration
    ssl_certificate /path/to/ssl/certificate.crt;
    ssl_certificate_key /path/to/ssl/private.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";
    
    # Static files
    location /static/ {
        alias /home/snmpmon/snmp-monitoring/static_files/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Media files
    location /media/ {
        alias /home/snmpmon/snmp-monitoring/media/;
    }
    
    # Health check
    location /health/ {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
    
    # Main application
    location / {
        proxy_pass http://snmpmon_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_buffering off;
        proxy_connect_timeout 60;
        proxy_read_timeout 60;
        proxy_send_timeout 60;
    }
}
```

### Production Optimizations

#### 10. Database Optimizations
```sql
-- PostgreSQL production tuning
-- Add to postgresql.conf
max_connections = 200
shared_buffers = 512MB
effective_cache_size = 2GB
maintenance_work_mem = 128MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200

-- Create indexes for performance
CREATE INDEX CONCURRENTLY idx_switches_status ON switches(status);
CREATE INDEX CONCURRENTLY idx_switches_last_update ON switches(last_update);
CREATE INDEX CONCURRENTLY idx_switches_branch_status ON switches(branch_id, status);
CREATE INDEX CONCURRENTLY idx_switches_ports_switch_port ON switches_ports(switch_id, port);
```

#### 11. Redis Configuration
```conf
# /etc/redis/redis.conf production settings
maxmemory 1gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

#### 12. Monitoring and Logging
```python
# Add to production settings
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/snmpmon/django.log',
            'maxBytes': 1024*1024*15,  # 15MB
            'backupCount': 10,
            'formatter': 'json',
        },
    },
    'loggers': {
        'snmp': {
            'handlers': ['file'],
            'level': 'INFO',
        },
    },
}
```

### Security Configuration

#### 13. Firewall Setup
```bash
# UFW firewall rules
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 80/tcp      # HTTP (redirect to HTTPS)
sudo ufw allow 443/tcp     # HTTPS
sudo ufw allow 161/udp     # SNMP (from monitoring network)
sudo ufw enable
```

#### 14. Backup Configuration
```bash
# Database backup script
#!/bin/bash
# /home/snmpmon/scripts/backup_db.sh

BACKUP_DIR="/home/snmpmon/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="snmp_monitoring"

mkdir -p $BACKUP_DIR

# Create database backup
pg_dump -h localhost -U snmpmon -d $DB_NAME | gzip > $BACKUP_DIR/snmp_db_$DATE.sql.gz

# Keep only last 7 days
find $BACKUP_DIR -name "snmp_db_*.sql.gz" -mtime +7 -delete

# Add to crontab
# 0 2 * * * /home/snmpmon/scripts/backup_db.sh
```

### Deployment Commands

#### 15. Start Services
```bash
# Enable and start all services
sudo systemctl enable snmpmon-web snmpmon-worker snmpmon-beat nginx postgresql redis-server
sudo systemctl start snmpmon-web snmpmon-worker snmpmon-beat nginx postgresql redis-server

# Check service status
sudo systemctl status snmpmon-web snmpmon-worker snmpmon-beat
```

#### 16. Initial Data Setup
```bash
# Run device discovery
python manage.py auto_discover_devices --update-existing --monitor-uplinks

# Run initial health check
python manage.py monitor_health --parallel --send-alerts

# Monitor uplinks
python manage.py monitor_uplinks --parallel --send-alerts
```

### Maintenance

#### 17. Log Rotation
```bash
# /etc/logrotate.d/snmpmon
/var/log/snmpmon/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 snmpmon snmpmon
    postrotate
        systemctl reload snmpmon-web
    endscript
}
```

#### 18. Monitoring Commands
```bash
# System monitoring
htop                                    # System resources
sudo systemctl status snmpmon-*        # Service status
sudo journalctl -f -u snmpmon-web     # Web service logs
sudo journalctl -f -u snmpmon-worker  # Worker logs

# Application monitoring
python manage.py collect_metrics       # Collect system metrics
python manage.py monitor_health        # Health check
curl https://your-domain.com/health/   # Health endpoint
```

### Troubleshooting

#### Common Issues
1. **High CPU Usage**: Scale Celery workers, optimize SNMP polling intervals
2. **Database Locks**: Tune PostgreSQL, add connection pooling
3. **Memory Usage**: Monitor Redis memory, tune cache settings
4. **SNMP Timeouts**: Adjust timeout values, check network connectivity

#### Performance Tuning
- Monitor SNMP response times
- Optimize database queries
- Use Redis for caching
- Scale horizontally with multiple workers
- Implement connection pooling

This production deployment provides a robust, scalable, and secure SNMP monitoring system ready for enterprise use.