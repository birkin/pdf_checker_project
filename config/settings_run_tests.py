"""
Django settings for `run_tests.py`, for github-ci.
"""

import logging
import pathlib

## load envars ------------------------------------------------------
"""
Not needed for github-ci.
"""

log = logging.getLogger(__name__)


## django PROJECT settings ------------------------------------------

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
# log.debug( f'BASE_DIR, ``{BASE_DIR}``' )

# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'abcd'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ADMINS = []

ALLOWED_HOSTS = []
CSRF_TRUSTED_ORIGINS = []

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'pdf_checker_app',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [f'{BASE_DIR}/pdf_checker_app/pdf_checker_app_templates'],
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

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'local_data.db',
    }
}

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

# TIME_ZONE = 'UTC'  ## the default
TIME_ZONE = 'America/New_York'

USE_I18N = True

# USE_TZ = True  ## the default
USE_TZ = False


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = '/tmp/'

# Email
SERVER_EMAIL = 'example@domain.edu'
EMAIL_HOST = 'localhost'
EMAIL_PORT = 1025

## user uploaded files ----------------------------------------------
MEDIA_ROOT = '/tmp/'
BDR_API_FILE_PATH_ROOT = '/tmp/'
PDF_UPLOAD_PATH = '/tmp/pdf_uploads'
"""
The two settings below prevent django from auto-running chmod on uploaded files
    (which can cause permission issues when using a shared volume)
    see: https://docs.djangoproject.com/en/5.2/ref/settings/#file-upload-permissions
"""
FILE_UPLOAD_PERMISSIONS = None
FILE_UPLOAD_DIRECTORY_PERMISSIONS = None

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

## reminder:
## "Each 'logger' will pass messages above its log-level to its associated 'handlers',
## ...which will then output messages above the handler's own log-level."
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'standard': {
            'format': '[%(asctime)s] %(levelname)s [%(module)s-%(funcName)s()::%(lineno)d] %(message)s',
            'datefmt': '%d/%b/%Y %H:%M:%S',
        },
    },
    'handlers': {
        # 'mail_admins': {
        #     'level': 'ERROR',
        #     'class': 'django.utils.log.AdminEmailHandler',
        #     'include_html': True,
        # },
        # 'logfile': {
        #     'level': os.environ.get('LOG_LEVEL', 'INFO'),  # add LOG_LEVEL=DEBUG to the .env file to see debug messages
        #     'class': 'logging.FileHandler',  # note: configure server to use system's log-rotate to avoid permissions issues
        #     'filename': os.environ['LOG_PATH'],
        #     'formatter': 'standard',
        # },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
    },
    'loggers': {
        'django.request': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'pdf_checker_app': {
            'handlers': ['console'],  # for ci, just output to console
            'level': 'DEBUG',  # messages above this will get sent to the `logfile` handler
            'propagate': False,
        },
        # 'django.db.backends': {  # re-enable to check sql-queries! <https://docs.djangoproject.com/en/5.2/ref/logging/#django-db-backends>
        #     'handlers': ['logfile'],
        #     'level': os.environ['LOG_LEVEL'],
        #     'propagate': False
        # },
    },
}

## cache settings ---------------------------------------------------
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

LOGIN_URL = '/foo/'

TEST_RUNNER = 'django.test.runner.DiscoverRunner'
# TEST_RUNNER = 'test_runner.JSONTestRunner'


## django APP settings ----------------------------------------------

# None!
