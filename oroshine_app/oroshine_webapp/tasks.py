from datetime import datetime, timedelta
from django.utils import timezone
from celery import shared_task
from django.conf import settings
from django.db import close_old_connections
from django.core.cache import cache
from django.template.loader import render_to_string
from .google_calendar import get_calendar_service
from .emails import send_appointment_emails, send_contact_emails, send_html_email
from .models import Appointment, Contact
from django.core.mail import send_mail
import logging

logger = logging.getLogger(__name__)




@shared_task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task to verify Celery is working"""
    print(f'Request: {self.request!r}')
    return 'Celery is working!'

@shared_task
def heartbeat():
    print("Celery Beat is alive!")



# ---------------------------------------------------
# WELCOME EMAIL TASK
# ---------------------------------------------------
@shared_task(bind=True, max_retries=3)
def send_welcome_email_task(self, user_id, username, email, is_social=False):
    """
    Send welcome email using 'emails/welcome_email.html' template.
    """
    close_old_connections()
    cache_key = f"welcome_email_sent:{user_id}"
    if cache.get(cache_key):
        logger.info(f"[Welcome Email] Already sent for user {user_id}")
        return "skipped"

    try:
        context = {
            'username': username,
            'is_social': is_social,
        }
        
        send_html_email(
            subject='Welcome to OroShine Dental Care! 🦷',
            template_name="emails/welcome_email.html",
            context=context,
            recipient_list=[email]
        )
        
        cache.set(cache_key, True, 60 * 60 * 24)  # 24 hours
        logger.info(f"[Welcome Email] Successfully sent for user {user_id}")
        return "sent"
    except Exception as e:
        logger.error(f"[Welcome Email] Failed for user {user_id}: {e}")
        raise self.retry(exc=e, countdown=10)


# ---------------------------------------------------
# APPOINTMENT EMAIL TASK
# ---------------------------------------------------
@shared_task(bind=True, max_retries=3)
def send_appointment_email_task(self, appointment_ulid):
    """
    Send User, Admin, and Doctor emails using HTML templates.
    """
    close_old_connections()
    cache_key = f"appointment_email_sent:{appointment_ulid}"
    if cache.get(cache_key):
        logger.info(f"[Email] Already sent for appointment {appointment_ulid}")
        return "skipped"

    try:
        appointment = Appointment.objects.select_related('doctor', 'user').get(ulid=appointment_ulid)
        send_appointment_emails(appointment)
        
        cache.set(cache_key, True, 60 * 60 * 24)
        logger.info(f"[Email] Successfully sent for appointment {appointment_ulid}")
        return "sent"
    except Appointment.DoesNotExist:
        logger.error(f"Appointment {appointment_ulid} not found")
        return "not_found"
    except Exception as e:
        logger.error(f"Error sending appointment email: {e}")
        raise self.retry(exc=e, countdown=10)


# ---------------------------------------------------
# APPOINTMENT STATUS UPDATE EMAIL TASK (NEW)
# ---------------------------------------------------
@shared_task(bind=True, max_retries=3)
def send_appointment_status_update_email_task(self, appointment_ulid, old_status, new_status):
    """
    Send status update email when appointment status changes in admin.
    """
    close_old_connections()
    
    try:
        from .emails import send_appointment_status_update_email
        
        appointment = Appointment.objects.select_related('doctor', 'user').get(ulid=appointment_ulid)
        send_appointment_status_update_email(appointment, old_status, new_status)
        
        logger.info(
            f"[Status Update Email] Sent for appointment {appointment_ulid}: "
            f"{old_status} → {new_status}"
        )
        return "sent"
    except Appointment.DoesNotExist:
        logger.error(f"[Status Update Email] Appointment {appointment_ulid} not found")
        return "not_found"
    except Exception as e:
        logger.error(f"[Status Update Email] Failed for {appointment_ulid}: {e}")
        raise self.retry(exc=e, countdown=10)


# ---------------------------------------------------
# CONTACT US EMAIL TASK
# ---------------------------------------------------
@shared_task(bind=True, max_retries=3)
def send_contact_email_task(self, contact_id):
    close_old_connections()
    cache_key = f"contact_email_sent:{contact_id}"
    if cache.get(cache_key):
        logger.info("[Contact Email] Skipped (already sent)")
        return "skipped"

    try:
        contact = Contact.objects.get(id=contact_id)
        send_contact_emails({
            "name": contact.name,
            "email": contact.email,
            "subject": contact.subject,
            "message": contact.message,
        })
        
        cache.set(cache_key, True, 86400)
        logger.info("[Contact Email] Sent for %s", contact.email)
        return "sent"
    except Contact.DoesNotExist:
        return "not_found"
    except Exception as e:
        logger.exception("[Contact Email] Failed")
        raise self.retry(exc=e, countdown=10)


# ---------------------------------------------------
# CONTACT RESOLUTION EMAIL TASK (NEW)
# ---------------------------------------------------
@shared_task(bind=True, max_retries=3)
def send_contact_resolution_email_task(self, contact_ulid):
    """
    Send resolution email when contact is marked as resolved in admin.
    """
    close_old_connections()
    cache_key = f"contact_resolution_email_sent:{contact_ulid}"
    
    if cache.get(cache_key):
        logger.info(f"[Resolution Email] Already sent for contact {contact_ulid}")
        return "skipped"
    
    try:
        from .emails import send_contact_resolution_email
        
        contact = Contact.objects.get(ulid=contact_ulid)
        send_contact_resolution_email(contact)
        
        cache.set(cache_key, True, 86400)  # 24 hours
        logger.info(f"[Resolution Email] Sent for contact {contact_ulid}")
        return "sent"
    except Contact.DoesNotExist:
        logger.error(f"[Resolution Email] Contact {contact_ulid} not found")
        return "not_found"
    except Exception as e:
        logger.exception(f"[Resolution Email] Failed for {contact_ulid}")
        raise self.retry(exc=e, countdown=10)


# ---------------------------------------------------
# PASSWORD RESET TASK
# ---------------------------------------------------
@shared_task(bind=True, max_retries=3)
def send_password_reset_email_task(self, email, reset_link, username):
    close_old_connections()
    try:
        send_html_email(
            subject="Reset your OroShine password",
            template_name="emails/password_reset_email.html",
            context={
                "username": username,
                "reset_link": reset_link,
            },
            recipient_list=[email],
        )
        return "sent"
    except Exception as e:
        logger.exception("[Password Reset] Failed")
        raise self.retry(exc=e, countdown=15)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=5, retry_kwargs={"max_retries": 3})
def send_password_reset_success_email_task(self, email, username):
    """
    Sends an HTML confirmation email after a successful password reset.
    """
    close_old_connections()
    try:
        send_html_email(
            subject="Your OroShine password has been changed ✓",
            template_name="emails/password_reset_success.html",
            context={
                "username": username,
            },
            recipient_list=[email],
        )
        logger.info("[Password Reset Success] Sent to %s", email)
        return "sent"
    except Exception as e:
        logger.exception("[Password Reset Success] Failed for %s", email)
        raise self.retry(exc=e, countdown=15)


# ---------------------------------------------------
# CALENDAR EVENT TASK - FIXED VERSION
# ---------------------------------------------------
@shared_task(
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
)
def create_calendar_event_task(self, appointment_ulid):
    """
    Create a Google Calendar event WITHOUT attendees to avoid 403 errors.
    Service accounts cannot invite attendees without Domain-Wide Delegation.
    """
    close_old_connections()
    logger.info("CALENDAR_ID=%s", settings.GOOGLE_CALENDAR_ID)

    try:
        appt = (
            Appointment.objects
            .select_related("doctor")
            .only(
                "ulid",
                "date",
                "time",
                "name",
                "email",
                "service",
                "message",
                "status",
                "calendar_event_id",
                "doctor__email"
            )
            .get(ulid=appointment_ulid)
        )

        # Idempotency check
        if appt.calendar_event_id:
            logger.info("[Calendar] Event already exists for %s", appointment_ulid)
            return {"status": "skipped", "reason": "already_exists"}

        # Status check
        if appt.status not in ["confirmed", "pending"]:
            logger.info("[Calendar] Skipping event creation for status: %s", appt.status)
            return {"status": "skipped", "reason": appt.status}

        # Doctor validation
        if not appt.doctor or not appt.doctor.email:
            logger.warning("[Calendar] Invalid doctor for appointment %s", appointment_ulid)
            return {"status": "invalid_doctor"}

        # Parse date and time
        appt_date = appt.date if not isinstance(appt.date, str) \
            else datetime.strptime(appt.date, "%Y-%m-%d").date()
        
        appt_time = appt.time
        if isinstance(appt_time, str):
            if len(appt_time.split(":")) == 2:
                appt_time += ":00"
            appt_time = datetime.strptime(appt_time, "%H:%M:%S").time()

        start_dt = timezone.make_aware(
            datetime.combine(appt_date, appt_time),
            timezone.get_current_timezone()
        )
        end_dt = start_dt + timedelta(minutes=30)

        # Create event payload WITHOUT attendees
        event = {
            "summary": f"Dental Appointment – {appt.service} | {appt.name}",
            "description": (
                f"Patient: {appt.name}\n"
                f"Patient Email: {appt.email}\n"
                f"Doctor Email: {appt.doctor.email}\n\n"
                f"Message:\n{appt.message or 'N/A'}\n\n"
                f"Note: Email invitations sent separately via email system."
            ),
            "start": {
                "dateTime": start_dt.isoformat(),
                "timeZone": "Asia/Kolkata",
            },
            "end": {
                "dateTime": end_dt.isoformat(),
                "timeZone": "Asia/Kolkata",
            },
            "location": (
                "Sai Dental Clinic, 203, 2nd Floor, Chandrangan Residency Tower, "
                "Above GP Parshik Bank, Diva East, Navi Mumbai"
            ),
            # REMOVED: "attendees" field - this causes the 403 error
            # Attendees will receive email notifications through your email system instead
        }

        logger.info("Using calendar: %s", settings.GOOGLE_CALENDAR_ID)
        logger.info("Calendar event payload: %s", event)

        # Create the event
        service = get_calendar_service()
        created_event = service.events().insert(
            calendarId=settings.GOOGLE_CALENDAR_ID,
            body=event,
            sendUpdates="none"  # Changed from "all" to "none" since we have no attendees
        ).execute()

        # Save the event ID
        Appointment.objects.filter(ulid=appointment_ulid).update(
            calendar_event_id=created_event["id"]
        )

        logger.info(
            "[Calendar] Event created appointment=%s event_id=%s",
            appointment_ulid,
            created_event["id"]
        )

        return {
            "status": "success",
            "event_id": created_event["id"],
            "event_link": created_event.get("htmlLink"),
        }

    except Appointment.DoesNotExist:
        logger.error("[Calendar] Appointment %s not found", appointment_ulid)
        return {"status": "not_found"}
    except Exception as exc:
        logger.exception("[Calendar] Failed to create event for %s", appointment_ulid)
        raise self.retry(exc=exc)
    finally:
        close_old_connections()




@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3})
def send_appointment_cancel_email_task(self, appointment_ulid):
    close_old_connections()

    cache_key = f"appointment_cancel_email_sent:{appointment_ulid}"
    if cache.get(cache_key):
        logger.info("[Cancel Email] Already sent for %s", appointment_ulid)
        return "skipped"

    try:
        from .emails import send_appointment_cancellation_email

        appt = Appointment.objects.select_related("user", "doctor").get(
            ulid=appointment_ulid
        )

        send_appointment_cancellation_email(appt)

        cache.set(cache_key, True, 86400)

        logger.info("[Cancel Email] Sent for %s", appointment_ulid)
        return "sent"

    except Appointment.DoesNotExist:
        logger.error("[Cancel Email] Appointment %s not found", appointment_ulid)
        return "not_found"

    except Exception as e:
        logger.exception("[Cancel Email] Failed for %s", appointment_ulid)
        raise self.retry(exc=e)
