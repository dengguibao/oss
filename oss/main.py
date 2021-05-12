import os
import sys
import django
from common.verify import verify_ip_addr


# setup django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "oss.settings")
django.setup()

try:
    production = sys.argv[1] == "production"
except IndexError:
    production = False

if production:
    import gunicorn.app.wsgiapp as wsgi

    default_port = 8000
    default_host = '0.0.0.0'

    try:
        host = sys.argv[2]
    except ValueError:
        host = default_host
    except IndexError:
        host = default_host

    if not verify_ip_addr(host):
        host = default_host

    try:
        port = int(sys.argv[3])
    except ValueError:
        port = default_port
    except IndexError:
        port = default_port

    if 0 < port > 65536:
        port = default_port

    # This is just a simple way to supply args to gunicorn
    sys.argv = [".", "oss.wsgi", "--bind=%s:%s" % (host, port),  "--workers=4"]

    wsgi.run()
else:
    from django.core.management import call_command

    call_command("runserver")
