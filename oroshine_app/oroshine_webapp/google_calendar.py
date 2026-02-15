from google.oauth2 import service_account
from googleapiclient.discovery import build
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def get_calendar_service(delegate_email=None):
    """
    Get Google Calendar service instance.
    
    Args:
        delegate_email: Email address to impersonate (for Domain-Wide Delegation).
                       If provided, the service account will act on behalf of this user.
    
    Returns:
        Google Calendar service instance
    """
    try:
        credentials = service_account.Credentials.from_service_account_info(
            settings.GOOGLE_SERVICE_ACCOUNT_INFO,
            scopes=settings.GOOGLE_SCOPES,
        )
        
        # If delegate_email is provided, use Domain-Wide Delegation
        if delegate_email:
            logger.info(f"Creating delegated credentials for {delegate_email}")
            credentials = credentials.with_subject(delegate_email)
        
        service = build(
            "calendar",
            "v3",
            credentials=credentials,
            cache_discovery=False,
        )
        
        logger.info("Calendar service created successfully")
        return service
        
    except Exception as e:
        logger.error(f"Failed to create calendar service: {e}")
        raise


def get_calendar_service_simple():
    """
    Simple calendar service without delegation (cannot invite attendees).
    Use this for basic calendar operations without attendee invitations.
    """
    return get_calendar_service(delegate_email=None)