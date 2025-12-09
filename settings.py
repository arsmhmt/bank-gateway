import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

SECRET_KEY = 'your-strong-secret-key'
DEBUG = os.environ.get("DJANGO_DEBUG", "False").lower() == "true"
ALLOWED_HOSTS = [
    "89.163.213.225",
    "lider-pay.com",
    "www.lider-pay.com",
    "127.0.0.1",
    "localhost",
]

AUTH_USER_MODEL = 'core.User'


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'core',
    'admin_panel',
    'provider_panel',
    'client_api',
    'branches',
    'site_panel',
    'card',
    'crypto',
    'crispy_forms',
    'crispy_bootstrap4',
]

MIDDLEWARE = [
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

ROOT_URLCONF = 'urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = Path(os.environ.get('STATIC_ROOT', BASE_DIR / 'staticfiles'))
MEDIA_URL = '/media/'
MEDIA_ROOT = Path(os.environ.get('MEDIA_ROOT', BASE_DIR / 'media'))
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Crispy Forms settings
CRISPY_TEMPLATE_PACK = 'bootstrap4'

CSRF_TRUSTED_ORIGINS = [
    'https://bank-paycrypt-978519205264.europe-west1.run.app',
    'https://bank.lider-pay.com',
    'https://*.lider-pay.com',
    'https://lider-pay.com',
]

if DEBUG:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"
else:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = 'Lax'

# Ensure Django knows when requests are secure behind a proxy (Cloud Run)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Internationalization
LANGUAGE_CODE = "tr"
TIME_ZONE = "Europe/Istanbul"
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Authentication redirects
LOGIN_URL = "/yonetim/login/"
LOGIN_REDIRECT_URL = "/yonetim/"
LOGOUT_REDIRECT_URL = "/yonetim/login/"

# Email / SMTP configuration for password reset and notifications
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "mail.lider-pay.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "no-reply@lider-pay.com")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = "Lider Pay <no-reply@lider-pay.com>"

# Base URL for external payment links (public payment domain)
PAYMENT_BASE_URL = os.environ.get("PAYMENT_BASE_URL", "https://lider-pay.com")
CARD_PSP_INIT_ENDPOINT = os.environ.get("CARD_PSP_INIT_ENDPOINT", "https://psp.example.com/api/checkout")
CARD_PSP_API_KEY = os.environ.get("CARD_PSP_API_KEY", "demo-api-key")
CARD_PSP_MERCHANT_ID = os.environ.get("CARD_PSP_MERCHANT_ID", "demo-merchant")
CRYPTO_COLD_WALLETS = {
    "USDT:TRC20": os.environ.get("CRYPTO_WALLET_USDT_TRC20", ""),
    "USDT:ERC20": os.environ.get("CRYPTO_WALLET_USDT_ERC20", ""),
    "BTC:MAINNET": os.environ.get("CRYPTO_WALLET_BTC_MAINNET", ""),
}
CRYPTO_WEBHOOK_SECRET = os.environ.get("CRYPTO_WEBHOOK_SECRET", "demo-crypto-secret")
CRYPTO_TRON_EXPLORER_API_URL = os.environ.get("CRYPTO_TRON_EXPLORER_API_URL", "")
CRYPTO_TRON_EXPLORER_API_KEY = os.environ.get("CRYPTO_TRON_EXPLORER_API_KEY", "")
CRYPTO_TRON_EXPLORER_TX_URL = os.environ.get(
    "CRYPTO_TRON_EXPLORER_TX_URL",
    "https://tronscan.org/#/transaction/",
)
CRYPTO_USDT_TRC20_CONTRACT = os.environ.get(
    "CRYPTO_USDT_TRC20_CONTRACT",
    "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
)
CRYPTO_TRC20_MIN_CONFIRMATIONS = int(os.environ.get("CRYPTO_TRC20_MIN_CONFIRMATIONS", "1"))
CRYPTO_TRC20_AMOUNT_TOLERANCE = os.environ.get("CRYPTO_TRC20_AMOUNT_TOLERANCE", "0.000001")
