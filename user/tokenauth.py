from rest_framework.authentication import TokenAuthentication
from .models import Profile
from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions, HTTP_HEADER_ENCODING
from django.core.cache import cache
from django.conf import settings
from common.func import get_client_ip
import time


class ExpireTokenAuthentication(TokenAuthentication):
    def authenticate(self, request):
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

        if time.time()-cache_latest_time > settings.TOKEN_EXPIRE_TIME:
            raise exceptions.AuthenticationFailed(_('Token expire.'))

        cache.set('token_%s' % key, (cache_ua, cache_ip, time.time(), cache_user))
        return cache_user, None
