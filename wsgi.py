import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paycrypt_bank_gw.settings')
application = get_wsgi_application()

from django.conf import settings
from whitenoise import WhiteNoise
application = WhiteNoise(application, root=settings.STATIC_ROOT)
