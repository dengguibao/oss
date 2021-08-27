from pymemcache.exceptions import MemcacheError
from django.contrib.auth.models import User
from rest_framework.authentication import BaseAuthentication
from user.models import Keys
from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions, HTTP_HEADER_ENCODING
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from django.core.cache import cache
from django.conf import settings
from common.func import get_client_ip
from django.urls import resolve
import time


class TokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        client_ip = get_client_ip(request)
        block_key = 'block_ip_%s' % client_ip
        try:
            block_times = cache.get(block_key)
        except (ConnectionRefusedError, MemcacheError):
            raise exceptions.APIException('memcached service is not ready!')

        if block_times and block_times >= 2:
            raise exceptions.APIException('your ip address is blocked, will be auto resume after 2 hours')

        # 记录1秒内某个ip的请求频率
        request_times = cache.get(client_ip)
        if not request_times:
            request_times = 0
        cache.set(client_ip, request_times+1, 1)

        # 当1秒内请求次数超过20次，将ip列入黑名单，加入黑名单次数达到2次后，禁止该ip访问
        # print(request_times)
        if request_times >= 30:
            if not block_times:
                block_times = 0
            cache.set(block_key, block_times+1, 7200)
            # 第一次提醒用户超过频率太高
            raise exceptions.ParseError('your operation frequency is too high')

        # 对外api使用access_key secret_key访问接口
        # 对外api可以不需要token，直接利用ak/sk找到对应的用户，然后进行default_permission检查
        # default_permission设置为IsAuthenticated，即只需要登陆即可
        if request.path.startswith('/api/objects'):
            ak = request.GET.get('access_key', None)
            sk = request.GET.get('secret_key', None)
            if ak and sk:
                try:
                    k = Keys.objects.get(user_access_key=ak, user_secret_key=sk)
                except Keys.DoesNotExist:
                    k = None

                if k and k.user.is_active:
                    if client_ip == k.allow_ip or k.allow_ip == '*':
                        self.verify_user_storage_is_expire(request, k.user)
                        return k.user, None
                    else:
                        raise exceptions.NotAcceptable('your ip not in allow ip list')

        auth = request.META.get('HTTP_AUTHORIZATION', b'')
        if isinstance(auth, str):
            # Work around django test client oddness
            auth = auth.encode(HTTP_HEADER_ENCODING)

        auth = auth.split()

        # 如果header中没有token，则返回None, 然后使用permission_class进行权限检查
        if not auth or auth[0].lower() != b'token':
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

    def verify_token_value(self, key, request):
        ua = request.META.get('HTTP_USER_AGENT', 'unknown')
        client_ip = get_client_ip(request)

        cache_token = cache.get('token_%s' % key)
        if not cache_token:
            raise exceptions.AuthenticationFailed(_('Invalid token. '))

        cache_ua, cache_ip, cache_latest_time, cache_user = cache_token
        if cache_ua != ua:
            raise exceptions.AuthenticationFailed(_('Invalid token. UserAgent not match.'))

        if cache_ip != client_ip:
            raise exceptions.AuthenticationFailed(_('Invalid Token. Client ip error.'))

        if time.time() - cache_latest_time > settings.TOKEN_EXPIRE_TIME:
            raise exceptions.AuthenticationFailed(_('Invalid token. Token expire.'))

        self.verify_user_storage_is_expire(request, cache_user)
        cache.set('token_%s' % key, (cache_ua, cache_ip, time.time(), cache_user))
        return cache_user, None

    def verify_user_storage_is_expire(self, request, user: User):
        if request.path.startswith('/api/objects') and not user.capacity_quota.valid():
            raise exceptions.NotAcceptable('storage is expired!')


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
            raise PermissionDenied()

        return wrapper

    return decorator
