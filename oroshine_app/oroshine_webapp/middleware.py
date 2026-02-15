
import logging
from django.core.cache import cache
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from .metrics import appointment_bookings, appointment_booking_failures, email_send_total, email_send_failures
import time

logger = logging.getLogger(__name__)




class BusinessMetricsMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if request.path == '/appointment/' and request.method == 'POST':
            if response.status_code == 200:
                appointment_bookings.labels(
                    status='success',
                    service=request.POST.get('service', 'unknown')
                ).inc()
            elif response.status_code == 409:
                appointment_booking_failures.labels(reason='slot_conflict').inc()
            elif response.status_code >= 400:
                appointment_booking_failures.labels(reason='validation_error').inc()
        return respons





class PrometheusMetricsMiddleware:
    """
    Add to settings.py:
    'your_app.metrics.PrometheusMetricsMiddleware',
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        endpoint = request.path
        if endpoint.startswith('/api/'):
            endpoint = '/api/*'
        elif endpoint.startswith('/metrics'):
            endpoint = '/metrics'

        http_requests_total.labels(
            method=request.method,
            endpoint=endpoint,
            status=response.status_code
        ).inc()

        return response

class RateLimitMiddleware(MiddlewareMixin):
    """Rate limiting middleware for API endpoints"""
    
    def process_request(self, request):
        # Only apply to API endpoints
        if not request.path.startswith('/api/'):
            return None
        
        # Skip for authenticated staff users
        if request.user.is_authenticated and request.user.is_staff:
            return None
        
        # Get client IP
        ip = self.get_client_ip(request)
        
        # Rate limit key
        cache_key = f'rate_limit:{ip}:{request.path}'
        
        # Get current request count
        requests = cache.get(cache_key, 0)
        
        # Allow 100 requests per minute
        if requests >= 100:
            logger.warning(f"Rate limit exceeded for IP: {ip}")
            return JsonResponse({
                'status': 'error',
                'message': 'Rate limit exceeded. Please try again later.'
            }, status=429)
        
        # Increment counter
        cache.set(cache_key, requests + 1, 60)  # 1 minute window
        
        return None
    
    @staticmethod
    def get_client_ip(request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class CacheControlMiddleware(MiddlewareMixin):
    """Add cache control headers"""
    
    def process_response(self, request, response):
        # Don't cache authenticated user pages
        if request.user.is_authenticated:
            response['Cache-Control'] = 'private, no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        else:
            # Cache public pages for 10 minutes
            if request.path in ['/', '/about/', '/services/', '/pricing/']:
                response['Cache-Control'] = 'public, max-age=600'
        
        return response


class LastActivityMiddleware(MiddlewareMixin):
    """Track user's last activity"""
    
    def process_request(self, request):
        if request.user.is_authenticated:
            cache_key = f'last_activity:{request.user.id}'
            cache.set(cache_key, timezone.now(), 300)  # 5 minutes
        
        return None


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Add security headers"""
    
    def process_response(self, request, response):
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        return response






def sanitize_input(text, max_length=None):
    """Sanitize user input to prevent XSS"""
    if not text:
        return ""
    
    # Remove any HTML tags
    clean_text = bleach.clean(text, tags=[], strip=True)
    
    # Limit length if specified
    if max_length:
        clean_text = clean_text[:max_length]
    
    return clean_text.strip()


def validate_phone(phone):
    """Validate phone number format"""
    if not phone:
        return True
    
    # Remove spaces and dashes
    phone = re.sub(r'[\s\-\(\)]', '', phone)
    
    # Check if it matches valid format
    pattern = r'^\+?1?\d{9,15}$'
    return re.match(pattern, phone) is not None


def check_rate_limit(request, key_suffix, max_attempts=3, timeout=1800):
    """
    Generic rate limiting function
    Returns (is_limited, attempts_remaining)
    """
    ip = get_client_ip(request)
    rate_limit_key = f'rate_limit:{ip}:{key_suffix}'
    
    attempts = cache.get(rate_limit_key, 0)
    
    if attempts >= max_attempts:
        return (True, 0)
    
    return (False, max_attempts - attempts)


def increment_rate_limit(request, key_suffix, timeout=1800):
    """Increment rate limit counter"""
    ip = get_client_ip(request)
    rate_limit_key = f'rate_limit:{ip}:{key_suffix}'
    attempts = cache.get(rate_limit_key, 0)
    cache.set(rate_limit_key, attempts + 1, timeout)


def clear_rate_limit(request, key_suffix):
    """Clear rate limit on successful action"""
    ip = get_client_ip(request)
    rate_limit_key = f'rate_limit:{ip}:{key_suffix}'
    cache.delete(rate_limit_key)


def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

