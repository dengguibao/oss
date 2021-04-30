from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import DjangoModelPermissions

from common.func import clean_post_data
from common.verify import verify_ip_addr
from .models import Keys


class KeysEndpoint(APIView):
    permission_classes = (DjangoModelPermissions,)
    model = Keys
    queryset = model.objects.none()

    def get(self, request):
        keys = request.user.keys
        return Response({
            'code': 0,
            'msg': 'success',
            'data': {
                'access_key': keys.user_access_key,
                'secret_key': keys.user_secret_key,
                'allow_ip': keys.allow_ip
            }
        })

    def put(self, request):
        fields = (
            ('allow_ip', str, verify_ip_addr),
        )
        data = clean_post_data(request.body, fields)
        self.queryset = request.user.keys
        if 'allow_ip' in data: self.queryset.set_allow_access(data['allow_ip'])
        self.queryset.change_user_key()
        return Response({
            'code': 0,
            'msg': 'success'
        })
