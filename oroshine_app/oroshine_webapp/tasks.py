import logging
import requests
from datetime import datetime, timedelta
from django.utils import timezone
from celery import shared_task
from django.conf import settings
from django.db import close_old_connections
from django.core.cache import cache
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.core.mail import EmailMultiAlternatives
from .google_calendar import get_calendar_service
from .emails import send_appointment_emails, send_contact_emails, send_html_email
from .models import Appointment, Contact
import logging
logger = logging.getLogger(__name__)

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
        # Context matching variables in welcome_email.html
        context = {
            'username': username,
            'is_social': is_social,
            # If your template needs a specific login URL or other data, add it here
        }

        # Use the helper to render and send
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
def send_appointment_email_task(self, appointment_id):
    """
    Send User, Admin, and Doctor emails using HTML templates.
    """
    close_old_connections()

    cache_key = f"appointment_email_sent:{appointment_id}"

    if cache.get(cache_key):
        logger.info(f"[Email] Already sent for appointment {appointment_id}")
        return "skipped"

    try:
        # Use select_related to fetch doctor and user efficiently
        appointment = Appointment.objects.select_related('doctor', 'user').get(id=appointment_id)
        
        # Call logic in emails.py to send all 3 emails (User/Admin/Doctor)
        send_appointment_emails(appointment)

        cache.set(cache_key, True, 60 * 60 * 24)
        logger.info(f"[Email] Successfully sent for appointment {appointment_id}")
        return "sent"

    except Appointment.DoesNotExist:
        logger.error(f"Appointment {appointment_id} not found")
        return "not_found"
    except Exception as e:
        logger.error(f"Error sending appointment email: {e}")
        raise self.retry(exc=e, countdown=10)


# ---------------------------------------------------
# CONTACT US EMAIL TASK
# ---------------------------------------------------
@shared_task(bind=True, max_retries=3)
def send_contact_email_task(self, contact_data):
    """
    Send Contact acknowledgment to User and Alert to Admin.
    Expects `contact_data` as a dictionary to avoid DB race conditions.
    """
    close_old_connections()
    try:
        # Call logic in emails.py
        send_contact_emails(contact_data)
        
        logger.info(f"[Contact Email] Sent for {contact_data.get('email')}")
        return "sent"
    except Exception as e:
        logger.error(f"Error sending contact email: {e}")
        raise self.retry(exc=e, countdown=10)


# ---------------------------------------------------
# PASSWORD RESET TASK
# ---------------------------------------------------
@shared_task(bind=True, max_retries=3)
def send_password_reset_email_task(self, email, reset_link, username):
    close_old_connections()

    try:
        context = {
            'user': {'get_username': username},
            'reset_link': reset_link,
        }

        send_html_email(
            subject="Reset your OroShine password 🔐",
            template_name="password_reset_email.html",
            context=context,
            recipient_list=[email]
        )

        logger.info(f"[Password Reset] Email sent to {email}")
        return "sent"

    except Exception as e:
        logger.error(f"[Password Reset] Failed for {email}: {e}")
        raise self.retry(exc=e, countdown=15)

# ---------------------------------------------------
# GOOGLE CALENDAR TASK
# ---------------------------------------------------


# @shared_task(
#     bind=True,
#     max_retries=3,
#     autoretry_for=(Exception,),
#     retry_backoff=True,
#     retry_jitter=True,
# )
# def create_calendar_event_task(self, appointment_id):
#     close_old_connections()

#     logger.info("CALENDAR_ID=%s", settings.GOOGLE_CALENDAR_ID)
#     logger.info("SCOPES=%s", settings.GOOGLE_SCOPES)

#     try:
#         appt = (
#             Appointment.objects
#             .select_related('doctor')
#             .only(
#                 'id', 'date', 'time', 'name', 'email',
#                 'service', 'message', 'status',
#                 'calendar_event_id',
#                 'doctor__email'
#             )
#             .get(id=appointment_id)
#         )

#         # -----------------------------
#         # Idempotency
#         # -----------------------------
#         if appt.calendar_event_id:
#             logger.info(f"[Calendar] Event already exists for {appointment_id}")
#             return {"status": "skipped"}

#         if appt.status not in ["confirmed", "pending"]:
#             return {"status": "skipped", "reason": appt.status}

#         if not appt.doctor or not appt.doctor.email:
#             return {"status": "invalid_doctor"}

#         # -----------------------------
#         # Date & Time
#         # -----------------------------
#         appt_date = appt.date if not isinstance(appt.date, str) \
#             else datetime.strptime(appt.date, "%Y-%m-%d").date()

#         appt_time = appt.time
#         if isinstance(appt_time, str):
#             if len(appt_time.split(":")) == 2:
#                 appt_time += ":00"
#             appt_time = datetime.strptime(appt_time, "%H:%M:%S").time()

#         start_dt = timezone.make_aware(
#             datetime.combine(appt_date, appt_time),
#             timezone.get_current_timezone()
#         )
#         end_dt = start_dt + timedelta(minutes=30)

#         # -----------------------------
#         # Google Event Payload
#         # -----------------------------
#         event = {
#             "summary": f"Dental Appointment – {appt.service} | {appt.name}",
#             "description": (
#                 f"Patient: {appt.name}\n"
#                 f"Patient Email: {appt.email}\n"
#                 f"Doctor Email: {appt.doctor.email}\n\n"
#                 f"Message:\n{appt.message or 'N/A'}"
#             ),
#             "start": {
#                 "dateTime": start_dt.isoformat(),
#                 "timeZone": "Asia/Kolkata",
#             },
#             "end": {
#                 "dateTime": end_dt.isoformat(),
#                 "timeZone": "Asia/Kolkata",
#             },
#             "location": (
#                 "Sai Dental Clinic, 203, 2nd Floor, Chandrangan Residency Tower, "
#                 "Above GP Parshik Bank, Diva East, Navi Mumbai"
#             ),
#             "attendees": [
#                 {"email": appt.email},
#                 {"email": appt.doctor.email},
#             ],
#             "reminders": {
#                 "useDefault": False,
#                 "overrides": [
#                     {"method": "email", "minutes": 1440},
#                     {"method": "popup", "minutes": 30},
#                 ],
#             },
#         }

#         # -----------------------------
#         # Google API Call
#         # -----------------------------
#         service = get_calendar_service()
#         created_event = service.events().insert(
#             calendarId=settings.GOOGLE_CALENDAR_ID,
#             body=event,
#             # sendUpdates="all",  # sends email invites
#         ).execute()

#         Appointment.objects.filter(id=appointment_id).update(
#             calendar_event_id=created_event["id"]
#         )

#         logger.info(
#             f"[Calendar] Event created appointment={appointment_id} "
#             f"event={created_event['id']}"
#         )

#         return {"status": "success", "event_id": created_event["id"]}

#     except Appointment.DoesNotExist:
#         return {"status": "not_found"}

#     except Exception as exc:
#         logger.exception("[Calendar] Failed to create event")
#         raise self.retry(exc=exc)

#     finally:
#         close_old_connections()








# update calender task  as above casuing trouble so little modifications , removed email reminders 

@shared_task(
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
)
def create_calendar_event_task(self, appointment_id):
    close_old_connections()

    logger.info("CALENDAR_ID=%s", settings.GOOGLE_CALENDAR_ID)

    try:
        appt = (
            Appointment.objects
            .select_related("doctor")
            .only(
                "id", "date", "time", "name", "email",
                "service", "message", "status",
                "calendar_event_id", "doctor__email"
            )
            .get(id=appointment_id)
        )

        # -----------------------------
        # Idempotency
        # -----------------------------
        if appt.calendar_event_id:
            logger.info("[Calendar] Event already exists for %s", appointment_id)
            return {"status": "skipped"}

        if appt.status not in ["confirmed", "pending"]:
            return {"status": "skipped", "reason": appt.status}

        if not appt.doctor or not appt.doctor.email:
            return {"status": "invalid_doctor"}

        # -----------------------------
        # Date & Time
        # -----------------------------
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

        # -----------------------------
        # Google Event (NO attendees)
        # -----------------------------
        event = {
            "summary": f"Dental Appointment – {appt.service} | {appt.name}",
            "description": (
                f"Patient: {appt.name}\n"
                f"Patient Email: {appt.email}\n"
                f"Doctor Email: {appt.doctor.email}\n\n"
                f"Message:\n{appt.message or 'N/A'}"
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
        }

        service = get_calendar_service()
        created_event = service.events().insert(
            calendarId=settings.GOOGLE_CALENDAR_ID,
            body=event
        ).execute()

        Appointment.objects.filter(id=appointment_id).update(
            calendar_event_id=created_event["id"]
        )

        logger.info(
            "[Calendar] Event created appointment=%s event=%s",
            appointment_id, created_event["id"]
        )

        return {
            "status": "success",
            "event_id": created_event["id"],
            "event_link": created_event.get("htmlLink"),
        }

    except Appointment.DoesNotExist:
        return {"status": "not_found"}

    except Exception as exc:
        logger.exception("[Calendar] Failed to create event")
        raise self.retry(exc=exc)

    finally:
        close_old_connections()
