"""
Custom exception handler and exceptions for the SNMP API.
Provides consistent error responses across the API.
"""
from rest_framework.views import exception_handler
from rest_framework.exceptions import APIException
from rest_framework import status
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that provides consistent error responses.
    
    Args:
        exc: The exception instance
        context: Context dictionary containing view, request, etc.
    
    Returns:
        Response object with standardized error format
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    # If response is None, it's not a DRF exception
    if response is None:
        # Handle Django's ValidationError
        if isinstance(exc, DjangoValidationError):
            response_data = {
                'error': 'Validation Error',
                'detail': exc.messages if hasattr(exc, 'messages') else str(exc),
                'status_code': status.HTTP_400_BAD_REQUEST
            }
            from rest_framework.response import Response
            response = Response(response_data, status=status.HTTP_400_BAD_REQUEST)
        
        # Handle Django's Http404
        elif isinstance(exc, Http404):
            response_data = {
                'error': 'Not Found',
                'detail': 'The requested resource was not found.',
                'status_code': status.HTTP_404_NOT_FOUND
            }
            from rest_framework.response import Response
            response = Response(response_data, status=status.HTTP_404_NOT_FOUND)
        
        # Handle other exceptions
        else:
            logger.error(f"Unhandled exception: {exc}", exc_info=True)
            response_data = {
                'error': 'Internal Server Error',
                'detail': 'An unexpected error occurred.',
                'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR
            }
            from rest_framework.response import Response
            response = Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Standardize the error response format
    if response is not None:
        custom_response_data = {
            'success': False,
            'error': response.data.get('detail', 'An error occurred'),
            'status_code': response.status_code,
        }
        
        # Include field errors if present
        if isinstance(response.data, dict):
            field_errors = {k: v for k, v in response.data.items() if k != 'detail'}
            if field_errors:
                custom_response_data['field_errors'] = field_errors
        
        response.data = custom_response_data
    
    return response


# ============================================================================
# Custom Exceptions
# ============================================================================

class SNMPConnectionError(APIException):
    """Raised when SNMP connection to device fails."""
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'Unable to connect to the device via SNMP.'
    default_code = 'snmp_connection_error'


class SNMPTimeoutError(APIException):
    """Raised when SNMP request times out."""
    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    default_detail = 'SNMP request timed out.'
    default_code = 'snmp_timeout'


class InvalidSNMPCredentials(APIException):
    """Raised when SNMP credentials are invalid."""
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = 'Invalid SNMP credentials.'
    default_code = 'invalid_snmp_credentials'


class DeviceNotReachable(APIException):
    """Raised when device is not reachable."""
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'Device is not reachable.'
    default_code = 'device_not_reachable'


class InvalidDeviceConfiguration(APIException):
    """Raised when device configuration is invalid."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid device configuration.'
    default_code = 'invalid_device_config'


class PollingInProgress(APIException):
    """Raised when a polling operation is already in progress."""
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'A polling operation is already in progress for this device.'
    default_code = 'polling_in_progress'


class InsufficientPermissions(APIException):
    """Raised when user lacks required permissions."""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'You do not have permission to perform this action.'
    default_code = 'insufficient_permissions'
