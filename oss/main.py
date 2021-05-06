import os
import sys
import django
import gunicorn.app.wsgiapp as wsgi

# setup django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "oss.settings")
django.setup()
sys.argv = [".", "oss.wsgi", "--bind=0.0.0.0:80", "--worker=4"]
wsgi.run()
