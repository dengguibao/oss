from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import DjangoModelPermissions

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
                'secret_key': keys.user_secret_key
            }
        })

    def put(self, request):
        request.user.keys.change_user_key()
        return Response({
            'code': 0,
            'msg': 'success'
        })
