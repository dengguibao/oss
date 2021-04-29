from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import DjangoModelPermissions

from buckets.models import BucketType
from common.func import clean_post_data
from common.verify import verify_max_length, verify_max_value, verify_pk


class BucketTypeEndpoint(APIView):
    model = BucketType
    permission_classes = (DjangoModelPermissions,)
    queryset = model.objects.none()

    fields = [
        ('*name', str, (verify_max_length, 10)),
        ('*price', float, (verify_max_value, 999))
    ]
    pk_field = (('*bucket_type_id', int, (verify_pk, model)),)

    def get(self):
        self.queryset = self.model.objects.all()
        return Response({
            'code': 1,
            'msg': 'success',
            'data': self.queryset.values()
        })

    def post(self, request):
        data = clean_post_data(request.body, tuple(self.fields))
        self.queryset, create = self.model.objects.update_or_create(**data)
        return Response({
            'code': 0,
            'msg': 'success',
            'data': self.queryset.values()
        })

    def put(self, request):
        self.fields.append(self.pk_field[0])
        data = clean_post_data(request.body, tuple(self.fields))
        self.queryset = self.model.objects.filter(pk=data['bucket_type_id'])
        self.queryset.update(**data)
        return Response({
            'code': 0,
            'msg': 'success'
        })

    def delete(self, request):
        data = clean_post_data(request.body, self.pk_field)
        self.model.objects.get(pk=data['bucket_type_id']).delete()
        return Response({
            'code': 0,
            'msg': 'success'
        })
