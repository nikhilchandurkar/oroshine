# utils/cache_helpers.py
# Create this file in: oroshine_webapp/utils/cache_helpers.py

"""
Centralized cache management utilities for the OroShine application.
Provides consistent caching patterns and invalidation strategies.
"""

from django.core.cache import cache
from django.db.models import Count, Q
from functools import wraps
import logging

logger = logging.getLogger(__name__)


# ==========================================
# CACHE KEY PATTERNS
# ==========================================

CACHE_KEYS = {
    'doctor': 'doctor:{email}',
    'doctors_active': 'active_doctors_list',
    'doctor_choices': 'doctor_form_choices',
    'slots': 'slots:{doctor.id}:{date}',
    'user_appointments': 'user_appointments:{user_id}',
    'user_stats': 'user_appointment_stats:{user_id}',
    'time_slots': 'time_slots_list',
    'services': 'active_services_list',
}


# ==========================================
# CACHE TIMEOUTS (in seconds)
# ==========================================

CACHE_TIMEOUTS = {
    'doctor': 3600,        # 30 minutes
    'doctors_list': 3600,  # 1 hour
    'slots': 180,          # 3 minutes (short for availability)
    'appointments': 300,   # 5 minutes
    'stats': 600,          # 10 minutes
    'static_data': 86400,  # 24 hours (time slots, services)
}


# ==========================================
# CACHE DECORATOR
# ==========================================

def cached_query(timeout=300, key_prefix='query'):
    """
    Decorator for caching database query results
    
    Usage:
        @cached_query(timeout=600, key_prefix='user_data')
        def get_user_data(user_id):
            return User.objects.get(id=user_id)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            cache_key = f"{key_prefix}:{func.__name__}:{':'.join(map(str, args))}"
            
            result = cache.get(cache_key)
            if result is None:
                result = func(*args, **kwargs)
                cache.set(cache_key, result, timeout)
                logger.debug(f"Cache miss: {cache_key}")
            else:
                logger.debug(f"Cache hit: {cache_key}")
            
            return result
        return wrapper
    return decorator


# ==========================================
# DOCTOR CACHING
# ==========================================

def get_doctor_cached(email):
    """Get doctor by email with caching"""
    cache_key = CACHE_KEYS['doctor'].format(email=email)
    doctor = cache.get(cache_key)
    
    if doctor is None:
        from oroshine_webapp.models import Doctor
        try:
            doctor = Doctor.objects.get(email=email, is_active=True)
            cache.set(cache_key, doctor, CACHE_TIMEOUTS['doctor'])
            logger.debug(f"Doctor cached: {email}")
        except Doctor.DoesNotExist:
            # Cache negative result to prevent repeated DB queries
            cache.set(cache_key, False, 300)
            logger.warning(f"Doctor not found: {email}")
            return None
    
    return doctor if doctor else None


def get_active_doctors_cached():
    """Get all active doctors with caching"""
    from oroshine_webapp.models import Doctor
    return Doctor.objects.active_doctors()


def invalidate_doctor_cache(email=None):
    """Invalidate doctor-related caches"""
    keys_to_delete = [
        CACHE_KEYS['doctors_active'],
        CACHE_KEYS['doctor_choices'],
    ]
    
    if email:
        keys_to_delete.append(CACHE_KEYS['doctor'].format(email=email))
    
    cache.delete_many(keys_to_delete)
    logger.info(f"Doctor cache invalidated: {email or 'all'}")


# ==========================================
# SLOT AVAILABILITY CACHING
# ==========================================

def get_booked_slots_cached(doctor, date):
    """Get booked slots for a doctor on a specific date"""
    cache_key = CACHE_KEYS['slots'].format(doctor=doctor.id, date=date)
    booked_slots = cache.get(cache_key)
    
    if booked_slots is None:
        from oroshine_webapp.models import Appointment
        booked_slots = set(
            Appointment.objects.filter(
                doctor=doctor.id,
                date=date,
                status__in=['pending', 'confirmed']
            ).values_list('time', flat=True)
        )
        cache.set(cache_key, booked_slots, CACHE_TIMEOUTS['slots'])
        logger.debug(f"Slots cached: {doctor} on {date}")
    
    return booked_slots


def invalidate_slots_cache(doctor, date):
    """Invalidate slot availability cache"""
    cache_key = CACHE_KEYS['slots'].format(doctor=doctor.id, date=date)
    cache.delete(cache_key)
    logger.debug(f"Slots cache invalidated: {doctor} on {date}")


# ==========================================
# USER APPOINTMENT CACHING
# ==========================================

def get_user_appointments_cached(user_id, limit=10):
    """Get user's appointments with caching"""
    cache_key = CACHE_KEYS['user_appointments'].format(user_id=user_id)
    appointments = cache.get(cache_key)
    
    if appointments is None:
        from oroshine_webapp.models import Appointment
        appointments = list(
            Appointment.objects.filter(user_id=user_id)
            .select_related('user')
            .only('id', 'date', 'time', 'service', 'doctor', 'status')
            .order_by('-date', '-time')[:limit]
        )
        cache.set(cache_key, appointments, CACHE_TIMEOUTS['appointments'])
        logger.debug(f"User appointments cached: {user_id}")
    
    return appointments


def get_user_appointment_stats_cached(user_id):
    """Get user's appointment statistics with caching"""
    cache_key = CACHE_KEYS['user_stats'].format(user_id=user_id)
    stats = cache.get(cache_key)
    
    if stats is None:
        from oroshine_webapp.models import Appointment
        stats = Appointment.objects.filter(user_id=user_id).aggregate(
            total=Count('id'),
            pending=Count('id', filter=Q(status='pending')),
            confirmed=Count('id', filter=Q(status='confirmed')),
            completed=Count('id', filter=Q(status='completed')),
            cancelled=Count('id', filter=Q(status='cancelled'))
        )
        cache.set(cache_key, stats, CACHE_TIMEOUTS['stats'])
        logger.debug(f"User stats cached: {user_id}")
    
    return stats


def invalidate_user_cache(user_id):
    """Invalidate all user-related caches"""
    keys_to_delete = [
        CACHE_KEYS['user_appointments'].format(user_id=user_id),
        CACHE_KEYS['user_stats'].format(user_id=user_id),
    ]
    cache.delete_many(keys_to_delete)
    logger.debug(f"User cache invalidated: {user_id}")


# ==========================================
# BULK CACHE OPERATIONS
# ==========================================

def invalidate_appointment_related_cache(appointment):
    """
    Invalidate all caches related to an appointment
    Called after creating, updating, or deleting an appointment
    """
    keys_to_delete = [
        CACHE_KEYS['slots'].format(
            doctor=appointment.doctor.id,
            date=appointment.date
        ),
        CACHE_KEYS['user_appointments'].format(user_id=appointment.user_id),
        CACHE_KEYS['user_stats'].format(user_id=appointment.user_id),
    ]
    
    cache.delete_many(keys_to_delete)
    logger.info(f"Appointment cache invalidated: {appointment.id}")


def warm_cache_for_date_range(doctor, start_date, end_date):
    """
    Pre-populate cache for a date range
    Useful for frequently accessed dates
    """
    from datetime import timedelta
    from oroshine_webapp.models import Appointment
    
    current_date = start_date
    while current_date <= end_date:
        cache_key = CACHE_KEYS['slots'].format(
            doctor=doctor.id,
            date=current_date
        )
        
        booked_slots = set(
            Appointment.objects.filter(
                doctor=doctor.id,
                date=current_date,
                status__in=['pending', 'confirmed']
            ).values_list('time', flat=True)
        )
        
        cache.set(cache_key, booked_slots, CACHE_TIMEOUTS['slots'])
        current_date += timedelta(days=1)
    
    logger.info(f"Cache warmed for {doctor} from {start_date} to {end_date}")


def clear_all_appointment_caches():
    """
    Clear all appointment-related caches
    Use sparingly - mainly for maintenance or testing
    """
    patterns = [
        'slots:*',
        'user_appointments:*',
        'user_stats:*',
        'doctor:*',
        'active_doctors_list',
        'doctor_form_choices',
    ]
    
    # Redis-specific: delete by pattern
    try:
        from django_redis import get_redis_connection
        conn = get_redis_connection("default")
        
        for pattern in patterns:
            keys = conn.keys(f"oroshine:{pattern}")  # Using your KEY_PREFIX
            if keys:
                conn.delete(*keys)
        
        logger.warning("All appointment caches cleared")
    except Exception as e:
        logger.error(f"Error clearing caches: {e}")


# ==========================================
# CACHE STATISTICS
# ==========================================

def get_cache_stats():
    """
    Get cache hit/miss statistics
    Useful for monitoring cache effectiveness
    """
    try:
        from django_redis import get_redis_connection
        conn = get_redis_connection("default")
        info = conn.info('stats')
        
        return {
            'hits': info.get('keyspace_hits', 0),
            'misses': info.get('keyspace_misses', 0),
            'hit_rate': (
                info.get('keyspace_hits', 0) / 
                (info.get('keyspace_hits', 0) + info.get('keyspace_misses', 1))
            ) * 100
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return {}