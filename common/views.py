from django.contrib.auth.models import User
from django.core.cache import cache
from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ParseError, NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from common.func import send_phone_verify_code
from common.captcha import Captcha
from user.models import Profile


@api_view(('GET',))
@permission_classes((AllowAny,))
def send_phone_verify_code_endpoint(request):
    if request.method == 'GET':
        username = request.GET.get('username', None)
        try:
            user = User.objects.select_related('profile').get(username=username)
            phone = user.profile.phone
        except User.DoesNotExist:
            user = None

        try:
            profile = Profile.objects.get(phone=username)
            phone = profile.phone
        except Profile.DoesNotExist:
            profile = None

        if not user and not profile:
            raise ParseError('not found this user')

        if not cache.get('phone_verify_code_%s' % phone):
            status_code, verify_code = send_phone_verify_code(phone)
            if status_code == 200:
                cache.set('phone_verify_code_%s' % phone, verify_code, 120)
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
