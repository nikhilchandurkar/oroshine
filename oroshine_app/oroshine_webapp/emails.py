import logging
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

logger = logging.getLogger(__name__)

def send_html_email(subject, template_name, context, recipient_list):
    """
    Utility to render HTML, create a plain text fallback, and send.
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
        msg.send()
        return True
    except Exception as e:
        logger.error(f"Failed to send email '{subject}' to {recipient_list}: {e}")
        # We re-raise to let Celery know it failed so it can retry
        raise e

def send_appointment_emails(appointment):
    """
    Sends 3 separate emails (User, Admin, Doctor) using HTML templates.
    """
    # Context dictionary matching your HTML variables (e.g., {{ appointment.name }})
    context = {'appointment': appointment}

    # 1. Patient Confirmation
    send_html_email(
        subject=f"Appointment Confirmed! ✅ - {appointment.service}",
        template_name="emails/appointment_user.html",
        context=context,
        recipient_list=[appointment.email]
    )

    # 2. Admin Notification
    # send_html_email(
    #     subject=f"🔔 New Booking: {appointment.name} - {appointment.service}",
    #     template_name="emails/appointment_admin.html",
    #     context=context,
    #     recipient_list=[settings.ADMIN_EMAIL]
    # )

    # 3. Doctor Notification (if applicable)
    if appointment.doctor and appointment.doctor.email:
        # Reusing admin template for doctor (or create specific appointment_doctor.html)
        send_html_email(
            subject=f"New Patient: {appointment.name}",
            template_name="emails/appointment_admin.html",
            context=context,
            recipient_list=[appointment.doctor.email]
        )

def send_contact_emails(contact_data):
    """
    Sends 'Contact Us' acknowledgement + Admin alert.
    """
    # contact_data is a dictionary or object containing name, email, subject, message, ip
    
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