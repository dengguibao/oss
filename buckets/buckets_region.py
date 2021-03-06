from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import DjangoModelPermissions

from buckets.models import BucketRegion
from common.func import validate_post_data
from common.verify import verify_max_length, verify_pk, verify_in_array, verify_url

import copy


class BucketRegionEndpoint(APIView):
    permission_classes = (DjangoModelPermissions,)
    model = BucketRegion
    queryset = model.objects.none()

    fields = [
        ('*name', str, (verify_max_length, 40)),
        ('*secret_key', str, (verify_max_length, 50)),
        ('*access_key', str, (verify_max_length, 32)),
        ('*server', str, verify_url),
        ('*type', str, (verify_max_length, 10)),
        ('*state', str, (verify_in_array, ('e', 'd', 's')))
    ]
    pk_field = (
        ('*reg_id', int, (verify_pk, model)),
    )

    def get(self, request):
        req_user = request.user
        self.queryset = self.model.objects.all()
        return Response({
            'code': 1,
            'msg': 'success',
            'data': [i.json for i in self.queryset] if req_user.is_superuser else self.queryset.values('name', 'reg_id')
        })

    def post(self, request):
        data = validate_post_data(request.body, tuple(self.fields))
        self.queryset, create = self.model.objects.update_or_create(**data)
        return Response({
            'code': 0,
            'msg': 'success',
            'data': self.queryset.json
        })

    def put(self, request):
        fields = copy.deepcopy(self.fields)
        fields.append(self.pk_field[0])
        data = validate_post_data(request.body, tuple(fields))
        self.queryset = self.model.objects.filter(pk=data['reg_id'])
        self.queryset.update(**data)
        return Response({
            'code': 0,
            'msg': 'success'
        })

    def delete(self, request):
        data = validate_post_data(request.body, self.pk_field)
        self.model.objects.get(pk=data['reg_id']).delete()
        return Response({
            'code': 0,
            'msg': 'success'
        })

    # @staticmethod
    # def clean_url(url):
    #     if 'https://' in url:
    #         return url[8:]
    #     if 'http://' in url:
    #         return url[7:]
    #     return url
