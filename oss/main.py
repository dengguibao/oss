import os
import sys

import django

# setup django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "oss.settings")
django.setup()

try:
    production = sys.argv[1] == "production"
except IndexError:
    production = False

if production:
    import gunicorn.app.wsgiapp as wsgi

    # This is just a simple way to supply args to gunicorn
    sys.argv = [".", "oss.wsgi", "--bind=0.0.0.0:8000", "--workers=4"]

    wsgi.run()
else:
    from django.core.management import call_command

    call_command("runserver")