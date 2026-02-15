# admin.py - Django admin with asynchronous email notifications using Celery
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count
from django.contrib import messages as admin_messages
from .models import (
    Service,
    Doctor,
    Appointment,
    Contact,
    UserProfile,
    Newsletter
)
from .tasks import (
    send_appointment_email_task,
    send_contact_email_task,
    send_appointment_status_update_email_task,
    send_contact_resolution_email_task,
)
import logging

logger = logging.getLogger(__name__)


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    """
    Admin interface for managing dental services.
    Allows adding, editing, and reordering services.
    """
    list_display = [
        'name',
        'code',
        'colored_icon',
        'price_display',
        'duration_display',
        'appointment_count',
        'is_active',
        'display_order'
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'code', 'description']
    ordering = ['display_order', 'name']
    readonly_fields = ['ulid', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'description', 'ulid')
        }),
        ('Pricing & Duration', {
            'fields': ('price', 'duration_minutes')
        }),
        ('Display Settings', {
            'fields': ('display_order', 'icon', 'color', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def colored_icon(self, obj):
        """Display icon with color"""
        if obj.icon:
            return format_html(
                '<i class="{}" style="color: {}; font-size: 20px;"></i>',
                obj.icon,
                obj.color
            )
        return '-'
    colored_icon.short_description = 'Icon'

    def price_display(self, obj):
        """Format price with currency symbol"""
        return f"₹{obj.price:,.2f}"
    price_display.short_description = 'Price'
    price_display.admin_order_field = 'price'

    def duration_display(self, obj):
        """Display duration in readable format"""
        hours = obj.duration_minutes // 60
        minutes = obj.duration_minutes % 60
        if hours > 0:
            return f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"
        return f"{minutes}m"
    duration_display.short_description = 'Duration'
    duration_display.admin_order_field = 'duration_minutes'

    def appointment_count(self, obj):
        """Count appointments for this service"""
        count = obj.appointments.count()
        if count > 0:
            return format_html(
                '<a href="/admin/core/appointment/?service__ulid={}">{} appointments</a>',
                obj.ulid,
                count
            )
        return '0'
    appointment_count.short_description = 'Appointments'

    def get_queryset(self, request):
        """Optimize queryset with annotation"""
        qs = super().get_queryset(request)
        return qs.annotate(appt_count=Count('appointments'))

    actions = ['activate_services', 'deactivate_services']

    def activate_services(self, request, queryset):
        """Bulk activate services"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} service(s) activated.')
    activate_services.short_description = 'Activate selected services'

    def deactivate_services(self, request, queryset):
        """Bulk deactivate services"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} service(s) deactivated.')
    deactivate_services.short_description = 'Deactivate selected services'


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    """Admin interface for doctors"""
    list_display = ['full_name', 'email', 'specialization', 'is_active', 'display_order']
    list_filter = ['is_active', 'specialization']
    search_fields = ['full_name', 'email']
    ordering = ['display_order', 'full_name']


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    """
    Admin interface for appointments with automatic async email notifications.
    Sends email to patient and doctor when status changes using Celery tasks.
    """
    list_display = [
        'ulid_short',
        'name',
        'service_display',
        'doctor',
        'date',
        'time',
        'colored_status',
        'created_at'
    ]
    list_filter = ['status', 'date', 'service', 'doctor']
    search_fields = ['name', 'email', 'phone', 'ulid']
    readonly_fields = ['ulid', 'created_at', 'updated_at', 'email_sent_at', 'calendar_created_at']
    date_hierarchy = 'date'
    
    fieldsets = (
        ('Appointment Info', {
            'fields': ('ulid', 'user', 'service', 'doctor', 'date', 'time', 'status')
        }),
        ('Patient Details', {
            'fields': ('name', 'email', 'phone', 'message')
        }),
        ('System Fields', {
            'fields': ('calendar_event_id', 'created_at', 'updated_at', 'email_sent_at', 'calendar_created_at'),
            'classes': ('collapse',)
        }),
    )

    def ulid_short(self, obj):
        """Display shortened ULID"""
        return f"{obj.ulid[:8]}..."
    ulid_short.short_description = 'ULID'

    def service_display(self, obj):
        """Display service with color"""
        if obj.service:
            return format_html(
                '<span style="color: {};">{}</span>',
                obj.service.color,
                obj.service.name
            )
        return '-'
    service_display.short_description = 'Service'
    service_display.admin_order_field = 'service__name'

    def colored_status(self, obj):
        """Display status with color coding"""
        colors = {
            'pending': '#FFA500',      # Orange
            'confirmed': '#28a745',    # Green
            'completed': '#007bff',    # Blue
            'cancelled': '#dc3545',    # Red
            'rescheduled': '#6c757d'   # Gray
        }
        color = colors.get(obj.status, '#000000')
        return format_html(
            '<strong style="color: {};">{}</strong>',
            color,
            obj.get_status_display()
        )
    colored_status.short_description = 'Status'
    colored_status.admin_order_field = 'status'

    def save_model(self, request, obj, form, change):
        """
        Override save to trigger async email notification when status changes.
        """
        # Track if this is an update and if status changed
        send_email = False
        old_status = None
        
        if change:
            # Editing existing appointment
            # Get the original object from database
            original = Appointment.objects.get(pk=obj.pk)
            old_status = original.status
            
            # Check if status changed
            if old_status != obj.status:
                send_email = True
                logger.info(
                    f"Status changed for appointment {obj.ulid}: {old_status} → {obj.status}"
                )
        
        # Save the object
        super().save_model(request, obj, form, change)
        
        # Queue async email notification if status changed
        if send_email:
            try:
                # Use Celery task for async email sending
                send_appointment_status_update_email_task.delay(
                    obj.ulid,
                    old_status,
                    obj.status
                )
                self.message_user(
                    request,
                    f'Status updated and notification email queued for {obj.email}',
                    level=admin_messages.SUCCESS
                )
            except Exception as e:
                logger.error(f"Failed to queue status update email: {e}")
                self.message_user(
                    request,
                    f'Status updated but failed to queue email notification: {str(e)}',
                    level=admin_messages.WARNING
                )

    actions = [
        'mark_as_confirmed',
        'mark_as_completed',
        'mark_as_cancelled',
        'resend_confirmation_email'
    ]

    def mark_as_confirmed(self, request, queryset):
        """Bulk confirm appointments and queue async emails"""
        updated_count = 0
        queued_count = 0
        
        for appointment in queryset:
            old_status = appointment.status
            if old_status != 'confirmed':
                appointment.status = 'confirmed'
                appointment.save()
                updated_count += 1
                
                # Queue async email notification
                try:
                    send_appointment_status_update_email_task.delay(
                        appointment.ulid,
                        old_status,
                        'confirmed'
                    )
                    queued_count += 1
                except Exception as e:
                    logger.error(f"Failed to queue confirmation email for {appointment.ulid}: {e}")
        
        self.message_user(
            request,
            f'{updated_count} appointment(s) confirmed. {queued_count} notification email(s) queued.'
        )
    mark_as_confirmed.short_description = '✅ Mark as Confirmed (send email)'

    def mark_as_completed(self, request, queryset):
        """Bulk complete appointments and queue async emails"""
        updated_count = 0
        queued_count = 0
        
        for appointment in queryset:
            old_status = appointment.status
            if old_status != 'completed':
                appointment.status = 'completed'
                appointment.save()
                updated_count += 1
                
                # Queue async email notification
                try:
                    send_appointment_status_update_email_task.delay(
                        appointment.ulid,
                        old_status,
                        'completed'
                    )
                    queued_count += 1
                except Exception as e:
                    logger.error(f"Failed to queue completion email for {appointment.ulid}: {e}")
        
        self.message_user(
            request,
            f'{updated_count} appointment(s) completed. {queued_count} notification email(s) queued.'
        )
    mark_as_completed.short_description = '✅ Mark as Completed (send email)'

    def mark_as_cancelled(self, request, queryset):
        """Bulk cancel appointments and queue async emails"""
        updated_count = 0
        queued_count = 0
        
        for appointment in queryset:
            old_status = appointment.status
            if old_status != 'cancelled':
                appointment.status = 'cancelled'
                appointment.save()
                updated_count += 1
                
                # Queue async email notification
                try:
                    send_appointment_status_update_email_task.delay(
                        appointment.ulid,
                        old_status,
                        'cancelled'
                    )
                    queued_count += 1
                except Exception as e:
                    logger.error(f"Failed to queue cancellation email for {appointment.ulid}: {e}")
        
        self.message_user(
            request,
            f'{updated_count} appointment(s) cancelled. {queued_count} notification email(s) queued.'
        )
    mark_as_cancelled.short_description = '❌ Mark as Cancelled (send email)'

    def resend_confirmation_email(self, request, queryset):
        """Resend confirmation emails for selected appointments (async)"""
        queued_count = 0
        
        for appointment in queryset:
            try:
                send_appointment_email_task.delay(appointment.ulid)
                queued_count += 1
            except Exception as e:
                logger.error(f"Failed to queue email for {appointment.ulid}: {e}")
        
        self.message_user(
            request,
            f'{queued_count} confirmation email(s) queued for sending.'
        )
    resend_confirmation_email.short_description = '📧 Resend Confirmation Email'


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    """
    Admin interface for contact submissions with async resolution emails.
    """
    list_display = [
        'ulid_short',
        'name',
        'email',
        'subject',
        'colored_status',
        'created_at'
    ]
    list_filter = ['is_resolved', 'created_at']
    search_fields = ['name', 'email', 'subject', 'message']
    readonly_fields = ['ulid', 'created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Contact Info', {
            'fields': ('ulid', 'user', 'name', 'email', 'subject')
        }),
        ('Message', {
            'fields': ('message',)
        }),
        ('Resolution', {
            'fields': ('is_resolved', 'resolved_at'),
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def ulid_short(self, obj):
        return f"{obj.ulid[:8]}..."
    ulid_short.short_description = 'ULID'

    def colored_status(self, obj):
        """Display resolution status with color"""
        if obj.is_resolved:
            return format_html(
                '<span style="color: #28a745;">✅ Resolved</span>'
            )
        return format_html(
            '<span style="color: #FFA500;">⏳ Pending</span>'
        )
    colored_status.short_description = 'Status'
    colored_status.admin_order_field = 'is_resolved'

    def save_model(self, request, obj, form, change):
        """
        Override save to trigger async resolution email when marked as resolved.
        """
        send_email = False
        
        if change:
            # Editing existing contact
            original = Contact.objects.get(pk=obj.pk)
            
            # Check if just marked as resolved
            if not original.is_resolved and obj.is_resolved:
                send_email = True
                logger.info(f"Contact {obj.ulid} marked as resolved")
        
        # Save the object
        super().save_model(request, obj, form, change)
        
        # Queue async resolution email
        if send_email:
            try:
                # Use Celery task for async email sending
                send_contact_resolution_email_task.delay(obj.ulid)
                self.message_user(
                    request,
                    f'Resolution email queued for {obj.email}',
                    level=admin_messages.SUCCESS
                )
            except Exception as e:
                logger.error(f"Failed to queue resolution email: {e}")
                self.message_user(
                    request,
                    f'Marked as resolved but failed to queue email notification: {str(e)}',
                    level=admin_messages.WARNING
                )

    actions = ['mark_as_resolved', 'mark_as_unresolved']

    def mark_as_resolved(self, request, queryset):
        """Bulk mark contacts as resolved and queue async emails"""
        from django.utils import timezone
        
        resolved_count = 0
        queued_count = 0
        
        for contact in queryset.filter(is_resolved=False):
            contact.is_resolved = True
            contact.resolved_at = timezone.now()
            contact.save()
            resolved_count += 1
            
            # Queue async resolution email
            try:
                send_contact_resolution_email_task.delay(contact.ulid)
                queued_count += 1
            except Exception as e:
                logger.error(f"Failed to queue resolution email for {contact.ulid}: {e}")
        
        self.message_user(
            request,
            f'{resolved_count} contact(s) marked as resolved. {queued_count} notification email(s) queued.'
        )
    mark_as_resolved.short_description = '✅ Mark as Resolved (send email)'

    def mark_as_unresolved(self, request, queryset):
        """Bulk mark contacts as unresolved"""
        updated = queryset.update(is_resolved=False, resolved_at=None)
        self.message_user(request, f'{updated} contact(s) marked as unresolved.')
    mark_as_unresolved.short_description = '⏳ Mark as Unresolved'


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Admin interface for user profiles"""
    list_display = ['user', 'phone', 'city', 'created_at']
    list_filter = ['city', 'created_at']
    search_fields = ['user__username', 'user__email', 'phone']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Newsletter)
class NewsletterAdmin(admin.ModelAdmin):
    """Admin interface for newsletter subscriptions"""
    list_display = ['email', 'is_active', 'subscribed_at']
    list_filter = ['is_active', 'subscribed_at']
    search_fields = ['email']