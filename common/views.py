from django.contrib.auth.models import User
from django.core.cache import cache
from django.http import HttpResponse, FileResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ParseError, NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from common.func import send_phone_verify_code
from common.captcha import Captcha


@api_view(('GET',))
@permission_classes((AllowAny,))
def send_phone_verify_code_endpoint(request):
    if request.method == 'GET':
        try:
            username = request.GET.get('username', None)
            user = User.objects.select_related('profile').get(username=username)
        except User.DoesNotExist:
            raise NotFound('not found this user')

        if not cache.get('phone_verify_code_%s' % user.profile.phone):
            status_code, verify_code = send_phone_verify_code(user.profile.phone)
            if status_code == 200:
                cache.set('phone_verify_code_%s' % user.profile.phone, verify_code, 120)
        else:
            raise ParseError(detail='verification code already send')

        return Response({
            'code': 0,
            'msg': 'success'
        })


@api_view(('GET',))
@permission_classes((AllowAny,))
def build_image_verify_code_endpoint(request):
    captcha = Captcha.instance()
    txt, img = captcha.generate_captcha()
    cache.set('img_verify_code_%s' % txt, True, 180)
    return HttpResponse(img, content_type="image/png")
