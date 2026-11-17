import os

from django.core.wsgi import get_wsgi_application

os.environ["DJANGO_SETTINGS_MODULE"] = "fabrique.settings"  # jamais celui d'un parent (Bramble Studio : config.settings)
application = get_wsgi_application()
