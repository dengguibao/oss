import os
import sys
import django
from django.conf import settings
from common.verify import verify_ip_addr


# setup django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "oss.settings")
django.setup()


try:
    arg1 = sys.argv[1]
except IndexError:
    print()
    print('usage: [initialization | production [--host <0.0.0.0>] [--port <8080>] [--worker <4>]]')
    print('--host: listen host, default 0.0.0.0')
    print('--port: listen port, default 8000, max 65535')
    print('--worker: worker thread number, default 4, max 16')
    print()
    sys.exit()

if arg1 not in ('production', 'initialization'):
    print('arg param err!')
    sys.exit()

if arg1 == "production":
    # import gunicorn.app.wsgiapp as wsgi
    import pyuwsgi

    default_port = 8080
    default_host = '0.0.0.0'
    default_worker = 4

    if '--host' in sys.argv:
        n = sys.argv.index('--host')
        try:
            host = sys.argv[n+1]
        except (ValueError, IndexError):
            host = default_host

        if not verify_ip_addr(host):
            host = default_host
    else:
        host = default_host

    if '--port' in sys.argv:
        n = sys.argv.index('--port')
        try:
            port = int(sys.argv[n+1])
        except (ValueError, IndexError):
            port = default_port

        if 0 <= port >= 65536:
            port = default_port
    else:
        port = default_port

    if '--worker' in sys.argv:
        n = sys.argv.index('--worker')
        try:
            worker = int(sys.argv[n+1])
        except ValueError:
            worker = default_worker
        except IndexError:
            worker = default_worker

        if 0 <= worker > 16:
            worker = default_worker

    else:
        worker = default_worker

    # This is just a simple way to supply args to gunicorn
    # sys.argv = [".", "oss.wsgi", "--bind=%s:%s" % (host, port),  "--workers=%s" % worker]
    #
    # wsgi.run()
    pyuwsgi.run([
        "--master",
        "--strict",
        "--need-app",
        "--module",
        ":".join(settings.WSGI_APPLICATION.rsplit(".", 1)),
        "--no-orphans",
        "--vacuum",
        "--auto-procname",
        # 因为python有GIL的原因，能过此选项目开启多线程
        "--enable-threads",
        # "--offload-threads=%s" % worker,
        "--processes=%s" % worker,
        "--thunder-lock",
        "--static-map=/static=%s/static" % settings.BASE_DIR,
        "--static-expires",
        # 90 days
        "/* 7776000",
        "--http=%s:%s" % (host, port)
    ])

elif arg1 == 'initialization':
    from django.core.management import call_command
    call_command('makemigrations')
    call_command('migrate')
    sys.exit()
