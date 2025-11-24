"""
Staging settings for Django project.
"""
import os
from .production import *

# Override some production settings for staging
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

# Less strict security for staging
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# More verbose logging for staging
LOGGING['loggers']['django']['level'] = 'DEBUG'
LOGGING['loggers']['snmp']['level'] = 'DEBUG'

# Email backend for staging
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'