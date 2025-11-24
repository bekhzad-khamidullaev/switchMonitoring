"""
Custom logging middleware for monitoring and metrics.
"""
import time
import logging
import json
from typing import Dict, Any, Optional
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpRequest, HttpResponse
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings


class LoggingMiddleware(MiddlewareMixin):
    """
    Middleware for logging requests, responses, and collecting metrics.
    """
    
    def __init__(self, get_response):
        super().__init__(get_response)
        self.logger = logging.getLogger('snmp.middleware.logging')
        self.performance_logger = logging.getLogger('snmp.performance')
        
    def process_request(self, request: HttpRequest) -> None:
        """Process incoming request."""
        # Record start time
        request.start_time = time.time()
        request.start_timestamp = timezone.now()
        
        # Generate unique request ID
        request.request_id = self._generate_request_id()
        
        # Log incoming request
        self._log_request(request)
        
        # Update request metrics
        self._update_request_metrics(request)
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Process outgoing response."""
        try:
            # Calculate response time
            if hasattr(request, 'start_time'):
                response_time = time.time() - request.start_time
                request.response_time = response_time
            else:
                response_time = 0
                request.response_time = 0
            
            # Log response
            self._log_response(request, response, response_time)
            
            # Update performance metrics
            self._update_performance_metrics(request, response, response_time)
            
            # Add custom headers
            if hasattr(request, 'request_id'):
                response['X-Request-ID'] = request.request_id
            response['X-Response-Time'] = f"{response_time:.3f}s"
            
        except Exception as e:
            self.logger.error(f"Error in process_response: {e}")
        
        return response
    
    def process_exception(self, request: HttpRequest, exception: Exception) -> Optional[HttpResponse]:
        """Process exceptions."""
        try:
            response_time = 0
            if hasattr(request, 'start_time'):
                response_time = time.time() - request.start_time
            
            # Log exception with context
            self._log_exception(request, exception, response_time)
            
            # Update error metrics
            self._update_error_metrics(request, exception)
            
        except Exception as e:
            # Fallback logging
            logging.getLogger('django').error(f"Error in process_exception: {e}")
        
        return None  # Don't handle the exception, let Django handle it
    
    def _generate_request_id(self) -> str:
        """Generate unique request ID."""
        import uuid
        return str(uuid.uuid4())[:8]
    
    def _log_request(self, request: HttpRequest) -> None:
        """Log incoming request."""
        try:
            user_info = self._get_user_info(request)
            
            log_data = {
                'event': 'request_start',
                'request_id': getattr(request, 'request_id', ''),
                'timestamp': timezone.now().isoformat(),
                'method': request.method,
                'path': request.path,
                'query_params': dict(request.GET),
                'user': user_info,
                'remote_addr': self._get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'content_length': request.META.get('CONTENT_LENGTH', 0),
            }
            
            # Add POST data for certain endpoints (excluding sensitive data)
            if request.method == 'POST' and self._should_log_post_data(request.path):
                log_data['post_data'] = self._sanitize_post_data(request.POST.dict())
            
            self.logger.info(
                f"Request started: {request.method} {request.path}",
                extra=log_data
            )
            
        except Exception as e:
            self.logger.error(f"Error logging request: {e}")
    
    def _log_response(self, request: HttpRequest, response: HttpResponse, response_time: float) -> None:
        """Log outgoing response."""
        try:
            log_data = {
                'event': 'request_complete',
                'request_id': getattr(request, 'request_id', ''),
                'timestamp': timezone.now().isoformat(),
                'method': request.method,
                'path': request.path,
                'status_code': response.status_code,
                'response_time': round(response_time, 3),
                'content_length': len(response.content) if hasattr(response, 'content') else 0,
                'user': self._get_user_info(request),
            }
            
            # Determine log level based on status code
            if response.status_code >= 500:
                log_level = 'error'
            elif response.status_code >= 400:
                log_level = 'warning'
            elif response_time > 5.0:  # Slow request
                log_level = 'warning'
            else:
                log_level = 'info'
            
            message = f"Request completed: {request.method} {request.path} - {response.status_code} ({response_time:.3f}s)"
            
            getattr(self.logger, log_level)(message, extra=log_data)
            
        except Exception as e:
            self.logger.error(f"Error logging response: {e}")
    
    def _log_exception(self, request: HttpRequest, exception: Exception, response_time: float) -> None:
        """Log exceptions."""
        try:
            log_data = {
                'event': 'request_exception',
                'request_id': getattr(request, 'request_id', ''),
                'timestamp': timezone.now().isoformat(),
                'method': request.method,
                'path': request.path,
                'exception_type': exception.__class__.__name__,
                'exception_message': str(exception),
                'response_time': round(response_time, 3),
                'user': self._get_user_info(request),
            }
            
            self.logger.error(
                f"Request exception: {request.method} {request.path} - {exception.__class__.__name__}: {exception}",
                extra=log_data,
                exc_info=True
            )
            
        except Exception as e:
            logging.getLogger('django').error(f"Error logging exception: {e}")
    
    def _get_user_info(self, request: HttpRequest) -> Dict[str, Any]:
        """Get user information for logging."""
        try:
            if hasattr(request, 'user') and not isinstance(request.user, AnonymousUser):
                return {
                    'id': request.user.id,
                    'username': request.user.username,
                    'is_staff': request.user.is_staff,
                    'is_superuser': request.user.is_superuser,
                }
            else:
                return {'anonymous': True}
        except Exception:
            return {'error': 'Failed to get user info'}
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        else:
            return request.META.get('REMOTE_ADDR', '')
    
    def _should_log_post_data(self, path: str) -> bool:
        """Determine if POST data should be logged for this path."""
        # Don't log sensitive endpoints
        sensitive_paths = ['/login/', '/admin/', '/api/auth/']
        return not any(sensitive in path for sensitive in sensitive_paths)
    
    def _sanitize_post_data(self, post_data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive data from POST data."""
        sensitive_fields = ['password', 'token', 'secret', 'key']
        sanitized = {}
        
        for key, value in post_data.items():
            if any(sensitive in key.lower() for sensitive in sensitive_fields):
                sanitized[key] = '[REDACTED]'
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _update_request_metrics(self, request: HttpRequest) -> None:
        """Update request metrics in cache."""
        try:
            # Get current metrics
            metrics_key = 'request_metrics'
            metrics = cache.get(metrics_key, {
                'total_requests': 0,
                'requests_by_method': {},
                'requests_by_path': {},
                'requests_by_hour': {},
                'last_updated': timezone.now().isoformat()
            })
            
            # Update counters
            metrics['total_requests'] += 1
            
            # By method
            method = request.method
            metrics['requests_by_method'][method] = metrics['requests_by_method'].get(method, 0) + 1
            
            # By path (limit to top-level paths to avoid explosion)
            path_parts = request.path.split('/')
            base_path = f"/{path_parts[1]}" if len(path_parts) > 1 else request.path
            metrics['requests_by_path'][base_path] = metrics['requests_by_path'].get(base_path, 0) + 1
            
            # By hour
            hour_key = timezone.now().strftime('%Y-%m-%d-%H')
            metrics['requests_by_hour'][hour_key] = metrics['requests_by_hour'].get(hour_key, 0) + 1
            
            # Keep only last 24 hours
            current_hour = timezone.now()
            cutoff_hour = current_hour - timezone.timedelta(hours=24)
            metrics['requests_by_hour'] = {
                k: v for k, v in metrics['requests_by_hour'].items() 
                if k >= cutoff_hour.strftime('%Y-%m-%d-%H')
            }
            
            metrics['last_updated'] = timezone.now().isoformat()
            
            # Store metrics (expire after 1 hour to prevent memory issues)
            cache.set(metrics_key, metrics, 3600)
            
        except Exception as e:
            self.logger.error(f"Error updating request metrics: {e}")
    
    def _update_performance_metrics(self, request: HttpRequest, response: HttpResponse, response_time: float) -> None:
        """Update performance metrics."""
        try:
            # Performance metrics
            perf_key = 'performance_metrics'
            perf_metrics = cache.get(perf_key, {
                'response_times': [],
                'status_codes': {},
                'slow_requests': [],
                'last_updated': timezone.now().isoformat()
            })
            
            # Add response time (keep last 1000)
            perf_metrics['response_times'].append(response_time)
            if len(perf_metrics['response_times']) > 1000:
                perf_metrics['response_times'] = perf_metrics['response_times'][-1000:]
            
            # Status code tracking
            status = str(response.status_code)
            perf_metrics['status_codes'][status] = perf_metrics['status_codes'].get(status, 0) + 1
            
            # Track slow requests (>2 seconds)
            if response_time > 2.0:
                slow_request = {
                    'path': request.path,
                    'method': request.method,
                    'response_time': round(response_time, 3),
                    'timestamp': timezone.now().isoformat(),
                    'status_code': response.status_code
                }
                perf_metrics['slow_requests'].append(slow_request)
                
                # Keep only last 100 slow requests
                if len(perf_metrics['slow_requests']) > 100:
                    perf_metrics['slow_requests'] = perf_metrics['slow_requests'][-100:]
            
            perf_metrics['last_updated'] = timezone.now().isoformat()
            
            # Store performance metrics
            cache.set(perf_key, perf_metrics, 3600)
            
            # Log slow requests
            if response_time > 5.0:
                self.performance_logger.warning(
                    f"Slow request detected: {request.method} {request.path} took {response_time:.3f}s",
                    extra={
                        'response_time': response_time,
                        'path': request.path,
                        'method': request.method,
                        'status_code': response.status_code
                    }
                )
            
        except Exception as e:
            self.logger.error(f"Error updating performance metrics: {e}")
    
    def _update_error_metrics(self, request: HttpRequest, exception: Exception) -> None:
        """Update error metrics."""
        try:
            error_key = 'error_metrics'
            error_metrics = cache.get(error_key, {
                'total_errors': 0,
                'errors_by_type': {},
                'errors_by_path': {},
                'recent_errors': [],
                'last_updated': timezone.now().isoformat()
            })
            
            # Update counters
            error_metrics['total_errors'] += 1
            
            # By exception type
            exception_type = exception.__class__.__name__
            error_metrics['errors_by_type'][exception_type] = error_metrics['errors_by_type'].get(exception_type, 0) + 1
            
            # By path
            path = request.path
            error_metrics['errors_by_path'][path] = error_metrics['errors_by_path'].get(path, 0) + 1
            
            # Recent errors (keep last 50)
            recent_error = {
                'timestamp': timezone.now().isoformat(),
                'path': request.path,
                'method': request.method,
                'exception_type': exception_type,
                'exception_message': str(exception)[:200],  # Limit message length
                'user': self._get_user_info(request)
            }
            error_metrics['recent_errors'].append(recent_error)
            if len(error_metrics['recent_errors']) > 50:
                error_metrics['recent_errors'] = error_metrics['recent_errors'][-50:]
            
            error_metrics['last_updated'] = timezone.now().isoformat()
            
            # Store error metrics
            cache.set(error_key, error_metrics, 3600)
            
        except Exception as e:
            logging.getLogger('django').error(f"Error updating error metrics: {e}")


class HealthCheckMiddleware(MiddlewareMixin):
    """
    Simple health check middleware for monitoring endpoints.
    """
    
    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """Handle health check requests."""
        if request.path == '/health/':
            from django.http import JsonResponse
            from django.db import connections
            from django.core.cache import cache
            
            health_status = {
                'status': 'healthy',
                'timestamp': timezone.now().isoformat(),
                'version': getattr(settings, 'VERSION', '1.0.0'),
                'checks': {}
            }
            
            # Database check
            try:
                db_conn = connections['default']
                db_conn.cursor()
                health_status['checks']['database'] = 'healthy'
            except Exception as e:
                health_status['checks']['database'] = f'unhealthy: {e}'
                health_status['status'] = 'unhealthy'
            
            # Cache check
            try:
                cache.set('health_check', 'ok', 30)
                if cache.get('health_check') == 'ok':
                    health_status['checks']['cache'] = 'healthy'
                else:
                    health_status['checks']['cache'] = 'unhealthy: cache write/read failed'
                    health_status['status'] = 'degraded'
            except Exception as e:
                health_status['checks']['cache'] = f'unhealthy: {e}'
                health_status['status'] = 'unhealthy'
            
            # Return appropriate status code
            status_code = 200 if health_status['status'] == 'healthy' else 503
            
            return JsonResponse(health_status, status=status_code)
        
        return None