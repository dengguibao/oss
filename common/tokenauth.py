from rest_framework.authentication import TokenAuthentication
from user.models import Profile
from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions, HTTP_HEADER_ENCODING
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from django.core.cache import cache
from django.conf import settings
from common.func import get_client_ip
from django.urls import resolve
import time


class ExpireTokenAuthentication(TokenAuthentication):
    def authenticate(self, request):
        client_ip = get_client_ip(request)
        if not cache.get(client_ip):
            cache.set(client_ip, 1, 1)

        request_times = cache.get(client_ip)
        cache.set(client_ip, request_times+1, 1)

        if request_times >= 20:
            raise exceptions.ParseError('request times too many')

        # 对外api使用access_key secret_key访问接口
        ak = request.GET.get('access_key', None)
        sk = request.GET.get('secret_key', None)
        if ak and sk:
            try:
                p = Profile.objects.get(access_key=ak, secret_key=sk)
            except Profile.DoesNotExist:
                p = None

            if p and p.user.is_active and request.META['PATH_INFO'].startswith('/api/objects'):
                return p.user, None

        auth = request.META.get('HTTP_AUTHORIZATION', b'')
        if isinstance(auth, str):
            # Work around django test client oddness
            auth = auth.encode(HTTP_HEADER_ENCODING)

        auth = auth.split()
        if not auth or auth[0].lower() != self.keyword.lower().encode():
            return None

        if len(auth) == 1:
            msg = _('Invalid token header. No credentials provided.')
            raise exceptions.AuthenticationFailed(msg)
        elif len(auth) > 2:
            msg = _('Invalid token header. Token string should not contain spaces.')
            raise exceptions.AuthenticationFailed(msg)

        try:
            token = auth[1].decode()
        except UnicodeError:
            msg = _('Invalid token header. Token string should not contain invalid characters.')
            raise exceptions.AuthenticationFailed(msg)

        return self.verify_token_value(token, request)

    @staticmethod
    def verify_token_value(key, request):
        ua = request.META.get('HTTP_USER_AGENT', 'unknown')
        client_ip = get_client_ip(request)

        cache_token = cache.get('token_%s' % key)
        if not cache_token:
            raise exceptions.AuthenticationFailed(_('Invalid token.'))

        cache_ua, cache_ip, cache_latest_time, cache_user = cache_token
        if cache_ua != ua:
            raise exceptions.AuthenticationFailed(_('UA not match.'))

        if cache_ip != client_ip:
            raise exceptions.AuthenticationFailed(_('Client ip error.'))

        if time.time() - cache_latest_time > settings.TOKEN_EXPIRE_TIME:
            raise exceptions.AuthenticationFailed(_('Token expire.'))

        cache.set('token_%s' % key, (cache_ua, cache_ip, time.time(), cache_user))
        return cache_user, None


def verify_permission(model_name: str, app_label: str = None):
    """
    验证权限
    """
    def decorator(func):
        def wrapper(request, *args, **kwargs):
            perms_map = {
                'GET': '{app_label}.view_{model_name}',
                'OPTIONS': None,
                'HEAD': None,
                'POST': '{app_label}.add_{model_name}',
                'PUT': '{app_label}.change_{model_name}',
                'PATCH': '{app_label}.change_{model_name}',
                'DELETE': '{app_label}.delete_{model_name}',
            }
            if not request.user and not request.user.is_authenticated and not request.user.is_active:
                raise NotAuthenticated('No login')
            r = resolve(request.path)
            perms = perms_map[request.method].format(
                app_label=app_label if app_label else 'auth' if r.app_name == 'user' else r.app_name,
                model_name=model_name
            )
            if request.user.has_perm(perms) and perms:
                return func(request, *args, **kwargs)
            raise PermissionDenied('user or role don\'t have this permission')

        return wrapper

    return decorator
