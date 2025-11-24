# SNMP Network Monitoring System

A comprehensive Django-based network monitoring system for SNMP-enabled devices with real-time health checks, alerting, and performance monitoring.

## 🚀 Features

### Core Functionality
- **Switch Management**: Complete CRUD operations for network switches
- **Real-time Monitoring**: Live health checks and status monitoring
- **SNMP Integration**: Auto-discovery and data collection via SNMP
- **Signal Analysis**: Optical signal level monitoring and alerting
- **Branch Management**: Multi-branch switch organization

### Monitoring & Alerting
- **Health Checks**: Comprehensive device health assessment
- **Performance Metrics**: Request/response time tracking
- **Alert System**: Email notifications for critical issues
- **Dashboard**: Real-time system overview and statistics
- **Export Tools**: Health reports and metrics export

### API & Integration
- **REST API**: Full REST API with Django REST Framework
- **Token Authentication**: Secure API access
- **Zabbix Integration**: Synchronization with Zabbix monitoring
- **Excel Export**: Data export to Excel format

## 🏗️ Architecture

### Service Layer Architecture
```
├── Views Layer (UI/API)
├── Service Layer (Business Logic)
├── Models Layer (Data)
└── External Services (SNMP, Email, Cache)
```

### Key Components
- **SwitchService**: Switch management and operations
- **SNMPService**: SNMP communication and device discovery
- **MonitoringService**: Health checks and alerting
- **LoggingMiddleware**: Request/response logging and metrics

## 📋 Requirements

- Python 3.8+
- Django 3.0+
- PostgreSQL 12+
- Redis 6.0+
- Celery 5.0+

## ⚡ Quick Start

### 1. Clone the Repository
```bash
git clone <repository-url>
cd snmp-monitoring
```

### 2. Set Up Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Run Setup Script
```bash
python scripts/setup_development.py
```

### 4. Configure Environment
Edit `.env` file with your settings:
```env
SECRET_KEY=your-secret-key
DB_NAME=snmp
DB_USER=snmp
DB_PASSWORD=your-password
REDIS_URL=redis://localhost:6379/0
```

### 5. Start Services
```bash
# Start Redis
redis-server

# Start Celery Worker
celery -A config worker -l info

# Start Celery Beat (for scheduled tasks)
celery -A config beat -l info

# Start Django Development Server
python manage.py runserver
```

## 🔧 Configuration

### Environment Settings
The application supports multiple environments:

- **Development**: `config.settings.development`
- **Staging**: `config.settings.staging`  
- **Production**: `config.settings.production`

Set the environment using:
```bash
export DJANGO_SETTINGS_MODULE=config.settings.production
```

### Database Configuration
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST', '127.0.0.1'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}
```

### Celery Configuration
Asynchronous tasks for:
- Switch status updates (every 5 minutes)
- Optical signal monitoring (every 4 hours)
- Inventory updates (daily at 09:00)
- Network discovery (daily at 03:00)

## 📊 Monitoring & Metrics

### Health Check Endpoints
- **System Health**: `/health/`
- **Monitoring Dashboard**: `/snmp/monitoring/`
- **Metrics View**: `/snmp/metrics/`

### API Endpoints
```
GET    /api/v1/switches/              # List switches
POST   /api/v1/switches/              # Create switch
GET    /api/v1/switches/{id}/         # Get switch details
PUT    /api/v1/switches/{id}/         # Update switch
DELETE /api/v1/switches/{id}/         # Delete switch
POST   /api/v1/switches/{id}/health_check/  # Run health check
GET    /api/v1/monitoring/            # System overview
GET    /api/v1/metrics/               # System metrics
```

### Authentication
```bash
# Get API Token
curl -X POST http://localhost:8000/api/v1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "your_username", "password": "your_password"}'

# Use Token
curl -H "Authorization: Token your_token_here" \
  http://localhost:8000/api/v1/switches/
```

## 🛠️ Management Commands

### Health Monitoring
```bash
# Run health checks on all switches
python manage.py monitor_health

# Check specific switch
python manage.py monitor_health --switch-id 123

# Check offline switches only
python manage.py monitor_health --offline-only

# Run parallel checks
python manage.py monitor_health --parallel --max-workers 10

# Send alert notifications
python manage.py monitor_health --send-alerts
```

### Metrics Collection
```bash
# Collect and display metrics
python manage.py collect_metrics

# Export to JSON
python manage.py collect_metrics --output json --file metrics.json

# Export to CSV
python manage.py collect_metrics --output csv --file metrics.csv
```

### SNMP Operations
```bash
# Update switch status
python manage.py update_switch_status

# Update optical information
python manage.py update_optical_info

# Discover network devices
python manage.py subnet_discovery
```

## 🔐 Security

### Production Security Settings
```python
# Enable in production
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

### API Security
- Token-based authentication
- Permission-based access control
- Rate limiting (configure as needed)
- HTTPS enforcement in production

## 📈 Performance

### Caching Strategy
- **Redis**: Session and application caching
- **QuerySet Optimization**: Select/prefetch related objects
- **Pagination**: Large dataset handling
- **Background Tasks**: Heavy operations via Celery

### Monitoring Performance
- Request/response time tracking
- Database query optimization
- Memory usage monitoring
- Error rate tracking

## 🧪 Testing

### Run Tests
```bash
# All tests
python manage.py test

# Specific app tests
python manage.py test snmp

# With coverage
pytest --cov=snmp tests/
```

### Test Categories
- **Unit Tests**: Service layer and models
- **Integration Tests**: API endpoints and workflows
- **Performance Tests**: Load testing with Locust

## 📝 Logging

### Log Levels and Files
- **Application Logs**: `logs/django.log`
- **Error Logs**: `logs/django_error.log`
- **Performance Logs**: Slow request tracking
- **Security Logs**: Authentication and authorization events

### Log Configuration
```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/django.log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'snmp': {
            'handlers': ['file'],
            'level': 'DEBUG',
        },
    },
}
```

## 🚀 Deployment

### Docker Deployment
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "config.wsgi:application"]
```

### Production Checklist
- [ ] Set `DEBUG = False`
- [ ] Configure proper `SECRET_KEY`
- [ ] Set up SSL/TLS certificates
- [ ] Configure email backend
- [ ] Set up log rotation
- [ ] Configure monitoring alerts
- [ ] Set up database backups
- [ ] Configure firewall rules

## 🤝 Contributing

### Development Workflow
1. Fork the repository
2. Create feature branch
3. Install pre-commit hooks
4. Make changes with tests
5. Submit pull request

### Code Quality Tools
- **Black**: Code formatting
- **isort**: Import sorting
- **Flake8**: Linting
- **mypy**: Type checking

## 📖 API Documentation

### Switch Management
```python
# List switches with filtering
GET /api/v1/switches/?status=true&branch=1&search=hostname

# Switch health check
POST /api/v1/switches/123/health_check/

# Auto-discover switch info
POST /api/v1/switches/123/discover_info/

# Test connectivity
POST /api/v1/switches/123/test_connectivity/
```

### Monitoring
```python
# System overview
GET /api/v1/monitoring/

# Run health checks
POST /api/v1/health-check/
{
    "switch_ids": [1, 2, 3],
    "send_alerts": true
}

# Get metrics
GET /api/v1/metrics/
```

## 📞 Support

### Troubleshooting
1. **Connection Issues**: Check SNMP community strings
2. **Performance Issues**: Review Celery worker status
3. **Database Issues**: Check PostgreSQL connection
4. **Cache Issues**: Verify Redis connectivity

### Common Issues
- **SNMP Timeouts**: Adjust timeout settings in SNMPService
- **High Memory Usage**: Check Celery task memory leaks
- **Slow Queries**: Enable query logging and optimization

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🔗 Links

- **Documentation**: [Link to detailed docs]
- **Issue Tracker**: [Link to issues]
- **API Documentation**: [Link to API docs]
- **Monitoring Dashboard**: `/snmp/monitoring/`

---

**Version**: 2.0.0  
**Last Updated**: $(date +'%Y-%m-%d')  
**Maintained by**: Your Team Name