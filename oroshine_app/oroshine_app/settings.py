"""
Production-ready Django settings for OroShine Dental App
"""

import os
from pathlib import Path
from decouple import config
from dotenv import load_dotenv
from kombu import Queue, Exchange


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
MEDIA_DIR = BASE_DIR / "media" / "avatars"
DEFAULT_AVATAR_PATH = MEDIA_DIR / "default.png"

# ==========================================
# SECURITY SETTINGS
# ==========================================
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1',
                       cast=lambda v: [s.strip() for s in v.split(',')])

# Security enhancements
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False 
CSRF_COOKIE_SECURE = False 
X_FRAME_OPTIONS = 'DENY'

SECURE_CROSS_ORIGIN_OPENER_POLICY = None
SECURE_CROSS_ORIGIN_EMBEDDER_POLICY = None
SECURE_CROSS_ORIGIN_RESOURCE_POLICY = None

# ==========================================
# APPLICATION DEFINITION
# ==========================================
INSTALLED_APPS = [
    'django_prometheus',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',

    # Third-party apps
    'crispy_forms',
    'crispy_bootstrap5',
    'django_celery_beat',
    'django_celery_results',
    'compressor',
    'django_minify_html',
    'imagekit',
    'django.contrib.humanize',
    'corsheaders',
    'django_extensions',
    'schema_viewer',



    # Social authentication
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.linkedin_oauth2',

    # Your app
    'oroshine_webapp',
]

SITE_ID =  config('SITE_ID',cast=int)

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'oroshine_webapp.middleware.RateLimitMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',
    'oroshine_webapp.metrics.PrometheusMetricsMiddleware',
]

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8000",
]

ROOT_URLCONF = 'oroshine_app.urls'

# ==========================================
# TEMPLATES
# ==========================================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'oroshine_app.wsgi.application'

# ==========================================
# DATABASE WITH CONNECTION POOLING
# ==========================================
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config('PG_DB', default='oroshine'),
        "USER": config('PG_USER', default='postgres'),
        "PASSWORD": config('PG_PASSWORD'),
        "HOST": config('PG_HOST', default='localhost'),
        "PORT": config('PG_PORT', default='5432'),
        "CONN_MAX_AGE": 200,
        "OPTIONS": {
            "connect_timeout": 10,
            "options": "-c statement_timeout=30000ms"
        }
    }
}

# ==========================================
# CACHING WITH REDIS
# ==========================================
REDIS_PASSWORD = config('REDIS_PASSWORD', '')
REDIS_HOST = config('REDIS_HOST', 'redis')
REDIS_PORT = config('REDIS_PORT', '6379',cast=int)
REDIS_DB = config('REDIS_DB', '1',cast=int)

CELERY_BROKER_URL = f'redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'
CELERY_RESULT_BACKEND = CELERY_BROKER_URL


CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}",
        "OPTIONS": {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'CONNECTION_POOL_KWARGS': {'max_connections': 25},
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'IGNORE_EXCEPTIONS': False,
        },
        "KEY_PREFIX": "oroshine",
        "TIMEOUT": 300,
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"
SESSION_COOKIE_AGE = 604800  # 1 week
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# ==========================================
# CELERY CONFIGURATION
# ==========================================
CELERY_BROKER_URL = config('CELERY_BROKER_URL')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Kolkata'

# Task tracking
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes
CELERY_RESULT_EXTENDED = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# Worker settings
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_MAX_TASKS_PER_CHILD = 50
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True

# Retry settings
CELERY_TASK_DEFAULT_RETRY_DELAY = 60
CELERY_TASK_MAX_RETRIES = 3

CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = False

# 




# ==========================================
# CELERY CONFIGURATION
# ==========================================

# ... (keep your existing broker/backend settings) ...

# Define the queues (You already have this, just double-checking)
CELERY_TASK_QUEUES = (
    Queue('calendar', Exchange('calendar'), routing_key='calendar'),
    Queue('email', Exchange('email'), routing_key='email'),
    Queue('default', Exchange('default'), routing_key='default'),
)

# 🚀 UPDATE THIS SECTION
# CELERY_TASK_ROUTES = {
#     # Route the email task to the 'email' queue
#     'oroshine_webapp.tasks.send_appointment_email_task': {
#         'queue': 'email',
#         'routing_key': 'email'
#     },
    
#     # Route the calendar task to the 'calendar' queue
#     'oroshine_webapp.tasks.create_calendar_event_task': {
#         'queue': 'calendar',
#         'routing_key': 'calendar'
#     },



# ==========================================
# CELERY CONFIGURATION
# ==========================================

CELERY_TASK_ROUTES = {
    # Email Queue
    'oroshine_webapp.tasks.send_appointment_email_task': {'queue': 'email'},
    'oroshine_webapp.tasks.send_welcome_email_task': {'queue': 'email'},
    'oroshine_webapp.tasks.send_contact_email_task': {'queue': 'email'},      
    'oroshine_webapp.tasks.send_password_reset_email_task': {'queue': 'email'}, 

    'oroshine_webapp.tasks.create_calendar_event_task': {'queue': 'calendar'},
}

# ==========================================
# AUTHENTICATION and all auth 
# ==========================================
AUTHENTICATION_BACKENDS = [
    # Needed to login by username in Django admin, regardless of `allauth`
    'django.contrib.auth.backends.ModelBackend',

    # `allauth` specific authentication methods, such as login by e-mail
    'allauth.account.auth_backends.AuthenticationBackend',
]

ACCOUNT_AUTHENTICATION_METHOD = 'username_email'
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USERNAME_REQUIRED = True
ACCOUNT_SIGNUP_PASSWORD_ENTER_TWICE = True
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_CONFIRM_EMAIL_ON_GET = True

# Social account settings
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_VERIFICATION = 'optional'
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_STORE_TOKENS = True

# Custom adapters
ACCOUNT_ADAPTER = "oroshine_webapp.adapters.CustomAccountAdapter"
SOCIALACCOUNT_ADAPTER = "oroshine_webapp.adapters.CustomSocialAccountAdapter"

# Redirect URLs
LOGIN_URL = '/custom_login/'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'
ACCOUNT_LOGOUT_REDIRECT_URL = 'home'
ACCOUNT_SIGNUP_REDIRECT_URL = '/custom-register'
SOCIALACCOUNT_LOGIN_ON_GET = True
ACCOUNT_LOGOUT_ON_GET = True

# Social provider settings
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'openid',
            'email',
            'profile',
        ],
        'AUTH_PARAMS': {
            'access_type': 'offline',   # REQUIRED
            'prompt': 'consent',        # REQUIRED (forces refresh_token)
        },
        'OAUTH_PKCE_ENABLED': True,
    },
    'linkedin_oauth2': {
        'SCOPE': ['r_basicprofile', 'r_emailaddress'],
        'PROFILE_FIELDS': [
            'id', 'first-name', 'last-name', 'email-address',
            'picture-url', 'public-profile-url',
        ]
    },
    'github': {
        'SCOPE': ['user', 'user:email'],
    }
}

ACCOUNT_RATE_LIMITS = {
    "login_failed": "5/1h",
    "email_verification": "3/1h",
    "password_reset": "5/1h",
}

# Username constraints
ACCOUNT_USERNAME_MIN_LENGTH = 3
ACCOUNT_USERNAME_BLACKLIST = ['admin', 'root', 'system', 'test', 'user']

# Password strength
ACCOUNT_PASSWORD_MIN_LENGTH = 8

# ==========================================
# PASSWORD VALIDATION
# ==========================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ==========================================
# INTERNATIONALIZATION
# ==========================================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# ==========================================
# STATIC & MEDIA FILES
# ==========================================
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'oroshine_webapp' / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
WHITENOISE_MAX_AGE = 31536000

STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder'
]

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ==========================================
# COMPRESSOR
# ==========================================
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True
COMPRESS_URL = STATIC_URL
COMPRESS_ROOT = STATIC_ROOT
COMPRESS_CSS_HASHING_METHOD = 'content'
COMPRESS_CSS_FILTERS = [
    'compressor.filters.css_default.CssAbsoluteFilter',
    'compressor.filters.cssmin.CSSMinFilter',
]
# COMPRESS_JS_FILTERS = ['compressor.filters.jsmin.JSMinFilter']

COMPRESS_JS_FILTERS =[]



# Compress output settings
COMPRESS_OUTPUT_DIR = 'CACHE'
COMPRESS_STORAGE = 'compressor.storage.CompressorFileStorage'

# Parser settings
COMPRESS_PARSER = 'compressor.parser.HtmlParser'
# ==========================================
# EMAIL CONFIGURATION SMTP
# ==========================================
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_HOST_USER = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default=EMAIL_HOST_USER)
ADMIN_EMAIL = config('ADMIN_EMAIL', default=EMAIL_HOST_USER)



# ==========================================
# GOOGLE CALENDAR API CONFIGURATION
# ==========================================
# GOOGLE CALENDAR API CONFIGURATION
# GOOGLE_CALENDAR_ID = config('GOOGLE_CALENDAR_ID', default='primary')

GOOGLE_CALENDAR_ID= config("GOOGLE_CALENDAR_ID")

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
]


# Reconstruct the Service Account Dictionary from Env Vars
GOOGLE_SERVICE_ACCOUNT_INFO = {
    "type": "service_account",
    "project_id": config("GOOGLE_PROJECT_ID"),
    "private_key_id": config("GOOGLE_PRIVATE_KEY_ID"),
    "private_key": config("GOOGLE_PRIVATE_KEY").replace('\\n', '\n'),
    "client_email": config("GOOGLE_CLIENT_EMAIL"),
    "client_id": config("GOOGLE_CLIENT_ID"),
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": config("GOOGLE_CLIENT_CERT_URL"),
}





DEFAULT_FROM_EMAIL = "OroShine Dental <no-reply@oroshine.com>"

FRONTEND_DOMAIN = "oroshine.com" 




# ==========================================
# LOGGING
# ==========================================
LOG_DIR = BASE_DIR / 'logs'
os.makedirs(LOG_DIR, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        }
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'django.log',
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 2,
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'celery': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'celery.log',
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 2,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'oroshine_webapp': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'celery': {
            'handlers': ['celery', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# ==========================================
# OTHER SETTINGS
# ==========================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

# Development tools
if DEBUG:
    INSTALLED_APPS += ["debug_toolbar"]
    MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")

    import socket
    hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
    INTERNAL_IPS = [
        "127.0.0.1",
        "localhost",
    ] + [".".join(ip.split(".")[:-1] + ["1"]) for ip in ips]

    DEBUG_TOOLBAR_CONFIG = {
        "SHOW_TOOLBAR_CALLBACK": lambda request: True,
        'INTERCEPT_REDIRECTS': False
    }

# File upload limits
FILE_UPLOAD_MAX_MEMORY_SIZE = 2621440  # 2 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 2621440  # 2 MB