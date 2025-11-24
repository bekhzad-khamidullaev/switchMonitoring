"""
Base service class with common functionality.
"""
import logging
from typing import Any, Dict, Optional, Type
from django.db import models
from django.core.exceptions import ValidationError
from django.db import transaction


class BaseService:
    """
    Base service class that provides common functionality for all services.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(f'{self.__class__.__module__}.{self.__class__.__name__}')
    
    def log_info(self, message: str, extra: Dict[str, Any] = None) -> None:
        """Log info message with optional extra context."""
        self.logger.info(message, extra=extra or {})
    
    def log_warning(self, message: str, extra: Dict[str, Any] = None) -> None:
        """Log warning message with optional extra context."""
        self.logger.warning(message, extra=extra or {})
    
    def log_error(self, message: str, extra: Dict[str, Any] = None) -> None:
        """Log error message with optional extra context."""
        self.logger.error(message, extra=extra or {})
    
    def log_debug(self, message: str, extra: Dict[str, Any] = None) -> None:
        """Log debug message with optional extra context."""
        self.logger.debug(message, extra=extra or {})
    
    @transaction.atomic
    def safe_create(self, model_class: Type[models.Model], **data) -> tuple[Optional[models.Model], Optional[str]]:
        """
        Safely create a model instance with transaction rollback on error.
        
        Returns:
            tuple: (instance, error_message)
        """
        try:
            instance = model_class.objects.create(**data)
            self.log_info(f"Created {model_class.__name__} with id {instance.pk}")
            return instance, None
        except ValidationError as e:
            error_msg = f"Validation error creating {model_class.__name__}: {e}"
            self.log_error(error_msg)
            return None, error_msg
        except Exception as e:
            error_msg = f"Unexpected error creating {model_class.__name__}: {e}"
            self.log_error(error_msg)
            return None, error_msg
    
    @transaction.atomic
    def safe_update(self, instance: models.Model, **data) -> tuple[bool, Optional[str]]:
        """
        Safely update a model instance with transaction rollback on error.
        
        Returns:
            tuple: (success, error_message)
        """
        try:
            for key, value in data.items():
                setattr(instance, key, value)
            instance.full_clean()
            instance.save()
            self.log_info(f"Updated {instance.__class__.__name__} with id {instance.pk}")
            return True, None
        except ValidationError as e:
            error_msg = f"Validation error updating {instance.__class__.__name__}: {e}"
            self.log_error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error updating {instance.__class__.__name__}: {e}"
            self.log_error(error_msg)
            return False, error_msg
    
    def handle_service_error(self, operation: str, error: Exception, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Standardized error handling for service operations.
        
        Returns:
            Dict with error details
        """
        error_details = {
            'success': False,
            'operation': operation,
            'error_type': error.__class__.__name__,
            'error_message': str(error),
            'context': context or {}
        }
        
        self.log_error(f"Service error in {operation}: {error}", extra=error_details)
        return error_details