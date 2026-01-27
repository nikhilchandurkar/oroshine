from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.cache import cache
from PIL import Image
from django.utils import timezone
from prometheus_client import Gauge

# ====================================
# DOCTOR MANAGER & MODEL
# ====================================

class DoctorManager(models.Manager):
    def active_doctors(self):
        """
        Return a QuerySet of active doctors (NOT a list).
        ⚠️ FIX: Return QuerySet directly for form compatibility.
        """
        return self.filter(is_active=True).order_by('display_order', 'full_name')

    def get_doctor_choices(self):
        """
        Return list of tuples (id, name) for ChoiceField.
        Caches choices for performance.
        """
        cache_key = 'doctor_form_choices'
        choices = cache.get(cache_key)

        if choices is None:
            doctors = self.active_doctors()
            choices = [(doc.id, doc.full_name) for doc in doctors]
            cache.set(cache_key, choices, 3600)

        return choices

class Doctor(models.Model):
    email = models.EmailField(unique=True, db_index=True)
    full_name = models.CharField(max_length=150)
    specialization = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    display_order = models.PositiveIntegerField(default=0)

    objects = DoctorManager()

    class Meta:
        ordering = ['display_order', 'full_name']

    def __str__(self):
        return f"Dr. {self.full_name}"

    @classmethod
    def cached_active_doctors(cls):
        """
        ⚠️ FIX: Return QuerySet for form compatibility.
        Cache only the IDs, return fresh QuerySet.
        """
        cache_key = "active_doctor_ids"
        ids = cache.get(cache_key)

        if ids is None:
            ids = list(
                cls.objects.filter(is_active=True)
                .values_list('id', flat=True)
                .order_by('display_order', 'full_name')
            )
            cache.set(cache_key, ids, 3600)

        # Return QuerySet (forms need QuerySet, not list)
        return cls.objects.filter(id__in=ids).order_by('display_order', 'full_name')

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Invalidate cache when doctors change
        cache.delete("active_doctor_ids")
        cache.delete("doctor_form_choices")

# ====================================
# CHOICES
# ====================================

TIME_SLOTS = (
    # Morning Slots: 09:00 AM – 02:00 PM
    ('09:00', '09:00 AM'), ('09:15', '09:15 AM'), ('09:30', '09:30 AM'), ('09:45', '09:45 AM'),
    ('10:00', '10:00 AM'), ('10:15', '10:15 AM'), ('10:30', '10:30 AM'), ('10:45', '10:45 AM'),
    ('11:00', '11:00 AM'), ('11:15', '11:15 AM'), ('11:30', '11:30 AM'), ('11:45', '11:45 AM'),
    ('12:00', '12:00 PM'), ('12:15', '12:15 PM'), ('12:30', '12:30 PM'), ('12:45', '12:45 PM'),
    ('13:00', '01:00 PM'), ('13:15', '01:15 PM'), ('13:30', '01:30 PM'), ('13:45', '01:45 PM'),
    ('14:00', '02:00 PM'),

    # Evening Slots: 06:00 PM – 09:00 PM
    ('18:00', '06:00 PM'), ('18:15', '06:15 PM'), ('18:30', '06:30 PM'), ('18:45', '06:45 PM'),
    ('19:00', '07:00 PM'), ('19:15', '07:15 PM'), ('19:30', '07:30 PM'), ('19:45', '07:45 PM'),
    ('20:00', '08:00 PM'), ('20:15', '08:15 PM'), ('20:30', '08:30 PM'), ('20:45', '08:45 PM'),
    ('21:00', '09:00 PM'),
)

STATUS_CHOICES = (
    ('pending', 'Pending'),
    ('confirmed', 'Confirmed'),
    ('cancelled', 'Cancelled'),
    ('completed', 'Completed'),
)

SERVICE_CHOICES = (
    ('checkup', 'General Checkup'),
    ('cleaning', 'Teeth Cleaning'),
    ('filling', 'Dental Filling'),
    ('extraction', 'Tooth Extraction'),
    ('root_canal', 'Root Canal'),
    ('whitening', 'Teeth Whitening'),
    ('braces', 'Braces Consultation'),
    ('emergency', 'Emergency'),
)

# Prometheus metrics
active_appointments = Gauge(
    'active_appointments_by_status',
    'Active appointments by status',
    ['status']
)

# ====================================
# CUSTOM MANAGERS
# ====================================

class UserProfileManager(models.Manager):
    def get_profile_with_user(self, user_id):
        return self.select_related('user').get(user_id=user_id)
    
    def active_profiles(self):
        return self.select_related('user').filter(user__is_active=True)

class AppointmentManager(models.Manager):
    def upcoming_for_user(self, user_id, limit=5):
        return (
            self.filter(
                user_id=user_id,
                status__in=['pending', 'confirmed'],
                date__gte=timezone.now().date()
            )
            .select_related('doctor')
            .only('id', 'date', 'time', 'service', 'status', 'doctor__full_name')
            .order_by('date', 'time')[:limit]
        )
    
    def booked_slots(self, date, doctor_id):
        return set(
            self.filter(
                date=date,
                doctor_id=doctor_id,
                status__in=['pending', 'confirmed']
            ).values_list('time', flat=True)
        )
    
    def with_counts_by_status(self, user_id):
        from django.db.models import Count, Q
        return self.filter(user_id=user_id).aggregate(
            total=Count('id'),
            pending=Count('id', filter=Q(status='pending')),
            confirmed=Count('id', filter=Q(status='confirmed')),
            completed=Count('id', filter=Q(status='completed')),
            cancelled=Count('id', filter=Q(status='cancelled'))
        )

class ContactManager(models.Manager):
    def recent_for_user(self, user_id, limit=5):
        return (
            self.filter(user_id=user_id)
            .only('id', 'subject', 'created_at', 'is_resolved')
            .order_by('-created_at')[:limit]
        )

# ====================================
# MODELS
# ====================================

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=15, blank=True, db_index=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(max_length=500, blank=True)
    city = models.CharField(max_length=100, blank=True, db_index=True)
    state = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=10, blank=True)
    welcome_email_sent = models.BooleanField(default=False)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=15, blank=True)
    medical_history = models.TextField(max_length=1000, blank=True)
    allergies = models.TextField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserProfileManager()

    class Meta:
        indexes = [
            models.Index(fields=['user', 'phone']),
            models.Index(fields=['city', 'created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Profile #{self.user_id}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Invalidate user cache on save
        cache.delete(f'user_profile:{self.user_id}')
        
        # Resize avatar efficiently
        if self.avatar and hasattr(self.avatar, 'path'):
            try:
                img = Image.open(self.avatar.path)
                if img.height > 300 or img.width > 300:
                    img.thumbnail((300, 300), Image.Resampling.LANCZOS)
                    img.save(self.avatar.path, optimize=True, quality=85)
            except Exception:
                pass

class Contact(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='contacts')
    name = models.CharField(max_length=250, db_index=True)
    email = models.EmailField(db_index=True)
    subject = models.CharField(max_length=250)
    message = models.TextField(max_length=3000)
    is_resolved = models.BooleanField(default=False, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = ContactManager()

    class Meta:
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['is_resolved', 'created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.subject} - {self.created_at.date()}"

class Service(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    duration_minutes = models.IntegerField(default=30)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['is_active', 'code']),
        ]

    def __str__(self):
        return self.name
    
    @classmethod
    def get_cached_active_services(cls):
        cache_key = 'active_services_list'
        services = cache.get(cache_key)
        
        if services is None:
            services = list(
                cls.objects.filter(is_active=True)
                .only('id', 'name', 'code', 'price')
                .order_by('name')
            )
            cache.set(cache_key, services, 86400)
        
        return services

class Appointment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='appointments', db_index=True)
    service = models.CharField(max_length=100, choices=SERVICE_CHOICES, db_index=True)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='appointments')
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=15)
    date = models.DateField(db_index=True)
    time = models.CharField(max_length=5, choices=TIME_SLOTS, db_index=True)
    message = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    calendar_event_id = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    calendar_created_at = models.DateTimeField(null=True, blank=True)

    objects = AppointmentManager()

    class Meta:
        ordering = ['-date', '-time']
        unique_together = [['doctor', 'date', 'time']]
        indexes = [
            models.Index(
                fields=['doctor', 'date', 'time', 'status'],
                name='idx_slot_lookup'
            ),
            models.Index(
                fields=['user', '-date'],
                name='idx_user_recent'
            ),
            models.Index(
                fields=['date', 'status'],
                name='idx_reminder_scan'
            ),
            models.Index(
                fields=['doctor', 'date'],
                name='idx_doctor_day'
            ),
        ]

    def __str__(self):
        doctor_name = f"Dr. {self.doctor.full_name}" if self.doctor else "No Doctor"
        return f"Appt#{self.id} - {doctor_name} - {self.date} {self.time}"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Invalidate relevant caches
        if self.doctor_id:
            cache.delete(f"slots:{self.doctor_id}:{self.date}")
        cache.delete(f'sidebar_appt:{self.user_id}')
        cache.delete(f'user_appointment_stats:{self.user_id}')

class Newsletter(models.Model):
    email = models.EmailField(unique=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    unsubscribed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-subscribed_at']
        indexes = [
            models.Index(fields=['is_active', 'subscribed_at']),
        ]

    def __str__(self):
        return self.email

@receiver(post_save, sender=Appointment)
def update_appointment_metrics(sender, instance, **kwargs):
    """Update appointment metrics on save"""
    from django.db.models import Count
    
    stats = Appointment.objects.values('status').annotate(count=Count('id'))
    
    for stat in stats:
        active_appointments.labels(status=stat['status']).set(stat['count'])