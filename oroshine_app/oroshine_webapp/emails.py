import logging
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from datetime import datetime, timedelta
from icalendar import Calendar, Event, vCalAddress, vText
from django.utils import timezone
import pytz

logger = logging.getLogger(__name__)


def create_ical_event(appointment):
    """
    Create an iCalendar event for the appointment.
    Returns the .ics file content as bytes.
    """
    try:
        cal = Calendar()
        cal.add('prodid', '-//OroShine Dental Care//Appointment//EN')
        cal.add('version', '2.0')
        cal.add('method', 'REQUEST')

        event = Event()
        
        # Parse appointment date and time
        appt_date = appointment.date if not isinstance(appointment.date, str) \
            else datetime.strptime(appointment.date, "%Y-%m-%d").date()
        
        appt_time = appointment.time
        if isinstance(appt_time, str):
            if len(appt_time.split(":")) == 2:
                appt_time += ":00"
            appt_time = datetime.strptime(appt_time, "%H:%M:%S").time()
        
        # Create timezone-aware datetime
        ist = pytz.timezone('Asia/Kolkata')
        start_dt = ist.localize(datetime.combine(appt_date, appt_time))
        end_dt = start_dt + timedelta(minutes=30)
        
        # Event details
        event.add('summary', f'Dental Appointment - {appointment.service}')
        event.add('dtstart', start_dt)
        event.add('dtend', end_dt)
        event.add('dtstamp', timezone.now())
        
        # Location
        location = "Sai Dental Clinic, 203, 2nd Floor, Chandrangan Residency Tower, Above GP Parshik Bank, Diva East, Navi Mumbai"
        event.add('location', vText(location))
        
        # Description
        description = f"""
Appointment Details:
Patient: {appointment.name}
Service: {appointment.service}
Doctor: {appointment.doctor.full_name if appointment.doctor else 'N/A'}
Phone: {appointment.phone}
Email: {appointment.email}

Message: {appointment.message or 'N/A'}

Location: {location}

Thank you for choosing OroShine Dental Care!
        """.strip()
        event.add('description', vText(description))
        
        # Organizer (clinic)
        organizer = vCalAddress(f'MAILTO:{settings.DEFAULT_FROM_EMAIL}')
        organizer.params['cn'] = vText('OroShine Dental Care')
        event.add('organizer', organizer)
        
        # Attendees (patient and doctor)
        attendee_patient = vCalAddress(f'MAILTO:{appointment.email}')
        attendee_patient.params['cn'] = vText(appointment.name)
        attendee_patient.params['role'] = vText('REQ-PARTICIPANT')
        attendee_patient.params['rsvp'] = vText('TRUE')
        event.add('attendee', attendee_patient)
        
        if appointment.doctor and appointment.doctor.email:
            attendee_doctor = vCalAddress(f'MAILTO:{appointment.doctor.email}')
            attendee_doctor.params['cn'] = vText(appointment.doctor.full_name)
            attendee_doctor.params['role'] = vText('REQ-PARTICIPANT')
            event.add('attendee', attendee_doctor)
        
        # Reminder - 24 hours before
        from icalendar import Alarm
        alarm = Alarm()
        alarm.add('action', 'DISPLAY')
        alarm.add('description', 'Reminder: Dental appointment tomorrow')
        alarm.add('trigger', timedelta(hours=-24))
        event.add_component(alarm)
        
        # Add event to calendar
        cal.add_component(event)
        
        return cal.to_ical()
        
    except Exception as e:
        logger.error(f"Failed to create iCal event: {e}")
        return None


def send_html_email(subject, template_name, context, recipient_list, ical_attachment=None):
    """
    Utility to render HTML, create a plain text fallback, and send.
    Optionally attaches an iCal file for calendar invites.
    
    Args:
        subject: Email subject
        template_name: Path to HTML template
        context: Template context dictionary
        recipient_list: List of recipient email addresses
        ical_attachment: Optional bytes content of .ics file
    """
    try:
        # Render HTML from the template folder
        html_content = render_to_string(template_name, context)
        # Auto-generate plain text from HTML
        text_content = strip_tags(html_content)

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipient_list
        )
        msg.attach_alternative(html_content, "text/html")
        
        # Attach calendar invite if provided
        if ical_attachment:
            msg.attach('appointment.ics', ical_attachment, 'text/calendar')
        
        msg.send()
        logger.info(f"Email sent successfully to {recipient_list}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email '{subject}' to {recipient_list}: {e}")
        # We re-raise to let Celery know it failed so it can retry
        raise e


def send_appointment_emails(appointment):
    """
    Sends 3 separate emails (User, Admin, Doctor) using HTML templates.
    Includes calendar invite (.ics) attachment for patient and doctor.
    """
    # Create calendar invite
    ical_content = create_ical_event(appointment)
    
    # Context dictionary matching your HTML variables
    context = {'appointment': appointment}

    # 1. Patient Confirmation (with calendar invite)
    send_html_email(
        subject=f"Appointment Confirmed! ✅ - {appointment.service}",
        template_name="emails/appointment_user.html",
        context=context,
        recipient_list=[appointment.email],
        ical_attachment=ical_content
    )

    # 2. Admin Notification (no calendar invite needed)
    send_html_email(
        subject=f"🔔 New Booking: {appointment.name} - {appointment.service}",
        template_name="emails/appointment_admin.html",
        context=context,
        recipient_list=[settings.ADMIN_EMAIL]
    )

    # 3. Doctor Notification (with calendar invite)
    if appointment.doctor and appointment.doctor.email:
        send_html_email(
            subject=f"New Patient: {appointment.name} - {appointment.service}",
            template_name="emails/appointment_doctor.html",  # Create separate template
            context=context,
            recipient_list=[appointment.doctor.email],
            ical_attachment=ical_content
        )


def send_appointment_status_update_email(appointment, old_status, new_status):
    """
    Send email notification when appointment status changes.
    Called from admin or views when status is updated.
    
    Args:
        appointment: Appointment instance
        old_status: Previous status
        new_status: New status
    """
    # Don't send email if status hasn't actually changed
    if old_status == new_status:
        return
    
    context = {
        'appointment': appointment,
        'old_status': old_status,
        'new_status': new_status,
    }
    
    # Map status to user-friendly messages
    status_messages = {
        'confirmed': {
            'subject': f'✅ Appointment Confirmed - {appointment.service}',
            'template': 'emails/appointment_confirmed.html'
        },
        'completed': {
            'subject': f'✅ Appointment Completed - {appointment.service}',
            'template': 'emails/appointment_completed.html'
        },
        'cancelled': {
            'subject': f'❌ Appointment Cancelled - {appointment.service}',
            'template': 'emails/appointment_cancelled.html'
        },
        'rescheduled': {
            'subject': f'🔄 Appointment Rescheduled - {appointment.service}',
            'template': 'emails/appointment_rescheduled.html'
        }
    }
    
    email_config = status_messages.get(new_status)
    
    if email_config:
        # Send to patient
        send_html_email(
            subject=email_config['subject'],
            template_name=email_config['template'],
            context=context,
            recipient_list=[appointment.email]
        )
        
        # Also notify doctor if confirmed or cancelled
        if new_status in ['confirmed', 'cancelled'] and appointment.doctor and appointment.doctor.email:
            send_html_email(
                subject=f"Patient Update: {appointment.name} - {new_status.title()}",
                template_name=email_config['template'],
                context=context,
                recipient_list=[appointment.doctor.email]
            )
        
        logger.info(f"Status update email sent for appointment {appointment.ulid}: {old_status} → {new_status}")


def send_appointment_cancellation_email(appointment):
    """
    Send HTML cancellation email to patient (and doctor).
    """

    context = {
        "appointment": appointment
    }

    # Send to patient
    send_html_email(
        subject=f"❌ Appointment Cancelled - {appointment.get_service_display()}",
        template_name="emails/appointment_cancelled_user.html",
        context=context,
        recipient_list=[appointment.email],
    )

    # Notify doctor
    if appointment.doctor and appointment.doctor.email:
        send_html_email(
            subject=f"Patient Cancelled: {appointment.name}",
            template_name="emails/appointment_cancelled_user.html",
            context=context,
            recipient_list=[appointment.doctor.email],
        )

    logger.info(f"Cancellation email sent for appointment {appointment.ulid}")




def send_contact_emails(contact_data):
    """
    Sends 'Contact Us' acknowledgement + Admin alert.
    """
    # 1. User Acknowledgement
    send_html_email(
        subject="We Received Your Message – OroShine Dental",
        template_name="emails/contact_user.html",
        context=contact_data,
        recipient_list=[contact_data['email']]
    )

    # 2. Admin Alert
    send_html_email(
        subject=f"New Inquiry: {contact_data['subject']}",
        template_name="emails/contact_admin.html",
        context=contact_data,
        recipient_list=[settings.ADMIN_EMAIL]
    )




def send_contact_resolution_email(contact):
    """
    Send email when contact inquiry is marked as resolved in admin.
    """
    context = {'contact': contact}
    
    send_html_email(
        subject="Your Inquiry Has Been Resolved - OroShine Dental",
        template_name="emails/contact_resolved.html",
        context=context,
        recipient_list=[contact.email]
    )
    
    logger.info(f"Resolution email sent for contact {contact.ulid}")