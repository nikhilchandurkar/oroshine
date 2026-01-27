from google.oauth2 import service_account
from googleapiclient.discovery import build
from django.conf import settings

def get_calendar_service():
    credentials = service_account.Credentials.from_service_account_info(
        settings.GOOGLE_SERVICE_ACCOUNT_INFO,
        scopes=settings.GOOGLE_SCOPES,
    )

    service = build(
        "calendar",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )

    return service
