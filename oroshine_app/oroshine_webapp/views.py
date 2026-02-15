from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.views import PasswordResetView
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.core.validators import validate_email, ValidationError
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import datetime
import logging
from django.views.decorators.cache import cache_page
from django.core.cache import cache
from functools import wraps
from django.db import transaction, IntegrityError
from django.contrib.auth.models import User
from django.utils.text import slugify
import re
import json
import random
from django.conf import settings
from django.http import HttpResponse,HttpResponseRedirect
from allauth.account.models import EmailAddress
from allauth.account.utils import send_email_confirmation
from django.urls import reverse_lazy,reverse
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.db.models import Count, Q

from ulid import ULID

from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from .models import (
    Contact, Appointment, UserProfile,
    Doctor, TIME_SLOTS, STATUS_CHOICES
)
from .forms import NewUserForm, UserProfileForm, AppointmentForm

from .tasks import (
    create_calendar_event_task,
    send_appointment_email_task,
    send_welcome_email_task,
    send_contact_email_task,
    send_password_reset_email_task,
    send_password_reset_success_email_task,
    send_appointment_cancel_email_task
)


from django.contrib.auth.views import PasswordResetConfirmView





logger = logging.getLogger(__name__)

LOCK_TTL = 30  # seconds

def prometheus_metrics(request):
    """Expose Prometheus metrics"""
    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)

# ==========================================
# RATE LIMITING DECORATOR
# ==========================================

def rate_limit(key_prefix, limit=5, window=900):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            identifier = request.META.get('REMOTE_ADDR', 'unknown')
            if request.user.is_authenticated:
                identifier = f"user_{request.user.id}"
            
            cache_key = f"ratelimit:{key_prefix}:{identifier}"
            attempts = cache.get(cache_key, 0)
            
            if attempts >= limit:
                msg = f'Too many attempts. Please try again in {window // 60} minutes.'
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'error', 'message': msg}, status=429)
                else:
                    messages.error(request, msg)
                    return redirect('custom_login')
            
            response = view_func(request, *args, **kwargs)
            
            # Only increment on failure
            is_failure = False
            if isinstance(response, JsonResponse):
                try:
                    data = json.loads(response.content.decode('utf-8'))
                    if data.get('status') == 'error': is_failure = True
                except: pass
            elif response.status_code >= 400:
                is_failure = True

            if is_failure:
                cache.set(cache_key, attempts + 1, window)
            
            return response
        return wrapper
    return decorator

# ==========================================
# HELPERS
# ==========================================

def invalidate_user_cache(user_id):
    keys = [
        f'user_profile:{user_id}',
        f'sidebar_appt:{user_id}',
        f'user_appointment_stats:{user_id}',
    ]
    for key in keys:
        cache.delete(key)

def is_valid_username(username):
    if not username or len(username) < 3 or len(username) > 150:
        return False, "Username must be between 3 and 150 characters"
    if not re.match(r'^[\w.@+-]+$', username):
        return False, "Username can only contain letters, numbers, and @/./+/-/_ characters"
    return True, ""

def is_valid_email(email):
    try:
        validate_email(email)
        return True, ""
    except ValidationError:
        return False, "Invalid email format"

def generate_username_suggestion(base_username):
    base = slugify(base_username) or "user"
    for i in range(1, 100):
        suggestion = f"{base}{i}"
        if not User.objects.filter(username__iexact=suggestion).exists():
            return suggestion
    return f"{base}{random.randint(100, 9999)}"

# ==========================================
# AUTH VIEWS
# ==========================================

@require_http_methods(["GET"])
@rate_limit('check_availability', limit=20, window=60)
def check_availability(request):
    username = request.GET.get('username', '').strip()
    email = request.GET.get('email', '').strip()
    
    if not username and not email:
        return JsonResponse({'status': 'error', 'message': 'Username or email required'}, status=400)
    
    cache_key = f"availability:{username or email}"
    cached_result = cache.get(cache_key)
    if cached_result:
        return JsonResponse(cached_result)
    
    response_data = {}
    
    if username:
        is_valid, error_msg = is_valid_username(username)
        if not is_valid:
            response_data = {'status': 'error', 'is_taken': True, 'message': error_msg}
        else:
            is_taken = User.objects.filter(username__iexact=username).exists()
            response_data = {
                'status': 'success',
                'is_taken': is_taken,
                'message': f'Username "{username}" is already taken' if is_taken else 'Username available',
                'suggestion': generate_username_suggestion(username) if is_taken else ''
            }
    
    elif email:
        is_valid, error_msg = is_valid_email(email)
        if not is_valid:
            response_data = {'status': 'error', 'is_taken': True, 'message': error_msg}
        else:
            is_taken = User.objects.filter(email__iexact=email).exists()
            response_data = {
                'status': 'success',
                'is_taken': is_taken,
                'message': 'Email already registered' if is_taken else 'Email available'
            }
    
    cache.set(cache_key, response_data, 300)
    return JsonResponse(response_data)

@rate_limit('register', limit=5, window=3600)
def register_request(request):
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == "POST":
        form = NewUserForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # 1. Save User
                    user = form.save()
                    
                    # 2. Create Profile
                    UserProfile.objects.get_or_create(user=user)
                    
                    #  Manual Allauth Setup (Crucial for Verification)
                    # We must manually create the EmailAddress object so Allauth knows about it
                    EmailAddress.objects.create(
                        user=user, 
                        email=user.email, 
                        primary=True, 
                        verified=False
                    )
                    
                    # This uses Allauth's built-in email sender
                    send_email_confirmation(request, user)

                    # 5. FIX: Queue Welcome Email Task
                    transaction.on_commit(
                        lambda: send_welcome_email_task.delay(
                            user.id, 
                            user.username, 
                            user.email, 
                            is_social=False
                        )
                    )

                    messages.success(request, f"Account created! Please check {user.email} to verify your account.")
                    return redirect('custom_login')

            except IntegrityError:
                messages.error(request, "Username or email already exists.")
            except Exception as e:
                logger.error(f"Registration error: {e}")
                messages.error(request, "An unexpected error occurred.")
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = NewUserForm()
    
    return render(request, "register.html", {"register_form": form})



@rate_limit('login', limit=5, window=900)
def login_request(request):
    if request.user.is_authenticated:
        return redirect('home')

    # --- AJAX Login Handler ---
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # ... (Keep your existing AJAX logic, but Add Verification Check below) ...
        pass 

    # --- Standard Login Handler ---
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()

            # FIX: Check if Email is Verified (Enforce Mandatory Setting)
            if not EmailAddress.objects.filter(user=user, verified=True).exists():
                # Allow login ONLY if it's a superuser, otherwise block
                if not user.is_superuser:
                    messages.error(request, "Please verify your email address before logging in.")
                    
                    # Optional: Resend verification link option here
                    # send_email_confirmation(request, user) 
                    
                    return render(request, "login.html", {"login_form": form})

            login(request, user)
            UserProfile.objects.get_or_create(user=user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect(request.GET.get('next', '/'))
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()

    return render(request, "login.html", {"login_form": form})



def logout_request(request):
    user_id = request.user.id if request.user.is_authenticated else None
    logout(request)
    if user_id:
        invalidate_user_cache(user_id)
    messages.success(request, "Logged out successfully.")
    return redirect("/")

# ==========================================
# PUBLIC PAGES (CACHED)
# ==========================================

def homepage(request):
    stats = cache.get('homepage_stats')
    if not stats:
        stats = {
            'total_appointments': Appointment.objects.filter(status='completed').count(),
            'active_users': UserProfile.objects.filter(user__is_active=True).count(),
            'satisfaction_rate': 88
        }
        cache.set('homepage_stats', stats, 1800)
    return render(request, 'index.html', {'stats': stats})

@cache_page(3600)
def about(request): return render(request, 'about.html')

@cache_page(3600)
def price(request): return render(request, 'price.html')

@cache_page(3600)
def service(request): return render(request, 'service.html')

@cache_page(3600)
def team(request): return render(request, "team.html")

@cache_page(3600)
def testimonial(request): return render(request, 'testimonial.html')

# ==========================================
# AJAX SLOT AVAILABILITY CHECK
# ==========================================

@require_http_methods(["POST"])
@login_required
def check_slots_ajax(request):
    doctor_id = request.POST.get('doctor_id')
    date = request.POST.get('date')

    if not doctor_id or not date:
        return JsonResponse({'status': 'error'}, status=400)

    cache_key = f"slots:{doctor_id}:{date}"

    booked = cache.get(cache_key)
    if booked is None:
        booked = set(
            Appointment.objects.filter(
                doctor_id=doctor_id,
                date=date,
                status__in=['pending', 'confirmed']
            ).values_list('time', flat=True)
        )
        cache.set(cache_key, booked, 300)

    slots = [
        {
            "time": t,
            "display": d,
            "is_available": t not in booked
        }
        for t, d in TIME_SLOTS
    ]

    return JsonResponse({'status': 'success', 'slots': slots})

# ==========================================
# APPOINTMENT BOOKING VIEW
# ==========================================

@login_required(login_url='/custom-login/')
def appointment(request):
    # AJAX POST: Book Appointment
    if request.method == "POST" and request.headers.get("X-Requested-With") == "XMLHttpRequest":
        form = AppointmentForm(request.POST)
        
        if not form.is_valid():
            logger.error(f"Form validation failed: {form.errors}")
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid input',
                'errors': form.errors
            }, status=400)

        data = form.cleaned_data
        doctor = data['doctor']
        date = data['date']
        time = data['time']

        logger.info(f"Booking attempt - Doctor: {doctor}, Date: {date}, Time: {time}")

        # Redis distributed lock
        lock_key = f"lock:slot:{doctor.id}:{date}:{time}"
        lock_value = str(ULID())

        if not cache.add(lock_key, lock_value, LOCK_TTL):
            logger.warning(f"Lock failed for slot {doctor.id}:{date}:{time}")
            return JsonResponse({
                'status': 'error',
                'message': 'Slot just booked by someone else. Please select another.'
            }, status=409)

        try:
            with transaction.atomic():
                # DB-level lock
                conflict = Appointment.objects.select_for_update().filter(
                    doctor=doctor,
                    date=date,
                    time=time,
                    status__in=['pending', 'confirmed']
                ).exists()

                if conflict:
                    logger.warning(f"Conflict detected for slot {doctor.id}:{date}:{time}")
                    return JsonResponse({
                        'status': 'error',
                        'message': 'This time slot is no longer available.'
                    }, status=409)

                # Create appointment
                appt = Appointment.objects.create(
                    user=request.user,
                    doctor=doctor,
                    date=date,
                    time=time,
                    service=data['service'],
                    name=data['name'],
                    email=data['email'],
                    phone=data.get('phone', ''),
                    message=data.get('message', ''),
                    status='pending'
                )

                logger.info(f"✓ Appointment created: ID={appt.ulid}")

                # Invalidate slot cache
                cache.delete(f"slots:{doctor.id}:{date}")

                # ⚠️ FIX: Queue tasks ONLY with .delay()
                transaction.on_commit(
                    lambda: send_appointment_email_task.delay(appt.ulid)
                )

                transaction.on_commit(
                    lambda: create_calendar_event_task.delay(appt.ulid)
                )

                logger.info(f"✓ Tasks queued for appointment {appt.ulid}")

            return JsonResponse({
                'status': 'success',
                'appointment_id': appt.ulid,
                'redirect_url': '/appointment'
            })

        except Exception as e:
            logger.exception(f"Error booking appointment: {e}")
            return JsonResponse({
                'status': 'error',
                'message': 'Failed to book appointment. Please try again.'
            }, status=500)
        
        finally:
            # Safe lock release
            if cache.get(lock_key) == lock_value:
                cache.delete(lock_key)

    # GET: Display Appointment Form
    form = AppointmentForm(initial={
        'name': request.user.get_full_name(),
        'email': request.user.email
    })

    return render(request, 'appointment.html', {
        'form': form,
        'time_slots': TIME_SLOTS,
    })


# ==========================================
# CANCEL APPOINTMENT
# ==========================================


@login_required
@require_http_methods(["POST"])
def cancel_appointment(request, appointment_id):
    try:
        with transaction.atomic():
            appt = Appointment.objects.select_for_update().get(
                ulid=appointment_id,
                user=request.user
            )

            if appt.status in ['cancelled', 'completed', 'confirmed']:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Cannot cancel {appt.status} appointment'
                }, status=400)

            appt.status = 'cancelled'
            appt.save(update_fields=['status', 'updated_at'])

            cache.delete(f"slots:{appt.doctor_id}:{appt.date}")

            transaction.on_commit(
                lambda: send_appointment_cancel_email_task.delay(appt.ulid)
            )

        invalidate_user_cache(request.user.id)

        return JsonResponse({
            'status': 'success',
            'message': 'Appointment cancelled successfully'
        })

    except Appointment.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Appointment not found'
        }, status=404)

# ==========================================
# PROFILE & CONTACT
# ==========================================
def contact(request):
    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.error(request, "Please login to submit.")
            return redirect('login')
            
        try:
            with transaction.atomic():
                contact_obj = Contact.objects.create(
                    user=request.user,
                    name=request.POST.get('name'),
                    email=request.POST.get('email'),
                    subject=request.POST.get('subject'),
                    message=request.POST.get('message')
                )
                
                # 🚀 TRIGGER ASYNC TASK
                transaction.on_commit(
                    lambda: send_contact_email_task.delay(contact_obj.id)
                )

            messages.success(request, "Message sent! We will contact you soon.")
            return redirect('home')
        except Exception as e:
            logger.error(f"Contact error: {e}")
            messages.error(request, "Error sending message.")
            
    return render(request, 'contact.html')


@login_required
def user_profile(request):
    user = request.user

    profile_cache_key = f"user_profile:{user.id}"
    stats_cache_key = f"user_appointment_stats:{user.id}"

    # =========================
    # PROFILE (cached)
    # =========================
    profile = cache.get(profile_cache_key)
    if not profile:
        profile, _ = UserProfile.objects.get_or_create(user=user)
        cache.set(profile_cache_key, profile, 600)

    # =========================
    # UPDATE PROFILE
    # =========================
    if request.method == "POST":
        form = UserProfileForm(
            request.POST,
            request.FILES,
            instance=profile
        )
        if form.is_valid():
            form.save()
            invalidate_user_cache(user.id)
            messages.success(request, "Profile updated successfully.")
            return redirect("user_profile")
    else:
        form = UserProfileForm(instance=profile)

    # =========================
    # APPOINTMENT STATS (cached)
    # =========================
    stats = cache.get(stats_cache_key)
    if not stats:
        stats = Appointment.objects.with_counts_by_status(user.id)
        cache.set(stats_cache_key, stats, 600)

    # =========================
    # APPOINTMENTS (paginated)
    # =========================
    appointments_qs = (
        Appointment.objects
        .filter(user=user)
        .select_related("doctor")
        .order_by("-date", "-created_at")
    )

    paginator = Paginator(appointments_qs, 10)
    page_number = request.GET.get("page")
    appointments_page = paginator.get_page(page_number)

    # =========================
    # CONTACT MESSAGES
    # =========================
    contacts = Contact.objects.recent_for_user(user.id)

    # =========================
    # CONTEXT
    # =========================
    context = {
        "form": form,
        "profile": profile,
        "appointments": appointments_page,
        "contacts": contacts,

        # Stats (safe defaults)
        "total_appointments": stats.get("total", 0),
        "pending_appointments": stats.get("pending", 0),
        "completed_appointments": stats.get("completed", 0),
    }

    return render(request, "profile.html", context)






class CustomPasswordResetView(PasswordResetView):
    template_name = "password_reset.html"
    success_url = reverse_lazy("password_reset_done")

    def form_valid(self, form):
        email = form.cleaned_data["email"]
        users = User.objects.filter(email__iexact=email)

        # 🔐 Enumeration-safe message
        messages.success(
            self.request,
            "If this email exists, a password reset link has been sent."
        )

        for user in users:
            token = self.token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))

            reset_link = (
                f"{self.request.scheme}://"
                f"{self.request.get_host()}"
                f"{reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})}"
            )

            name = user.first_name or user.get_username() or "User"

            send_password_reset_email_task.delay(
                email=user.email,
                reset_link=reset_link,
                username=name
            )

        return HttpResponseRedirect(self.success_url)






class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    """
    Overrides Django's PasswordResetConfirmView so that after the user
    successfully sets their new password we queue an async confirmation email.

    Django's stock flow:
        1. GET  → validates uid + token, renders the form (or an invalid-link page)
        2. POST → validates the new password, calls reset_password() which calls
                  user.set_password() + user.save(), then redirects to success_url.

    We override form_valid() because that is the single method called ONLY when
    the new password has already been persisted to the database.  At that point
    self.user is guaranteed to be the freshly-updated User instance.
    """

    template_name = "password_reset_confirm.html"
    success_url = reverse_lazy("password_reset_complete")

    def form_valid(self, form):
        """
        Called by Django after SetPasswordForm.save() has already run
        (i.e. the password is already hashed & written to the DB).
        We grab the user from the form and fire the async email task.
        """
        # The user whose password was just changed – set by Django internals
        user = form.user  # This is the resolved user from the uid in the URL

        # Queue the success email — runs outside this request/response cycle
        send_password_reset_success_email_task.delay(
            email=user.email,
            username=user.first_name or user.get_username() or "User",
        )

        # Let Django finish its normal redirect to success_url
        return super().form_valid(form)