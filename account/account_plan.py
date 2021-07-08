from rest_framework.views import APIView
from rest_framework.response import Response
from common.func import verify_super_user, validate_post_data
from rest_framework.exceptions import PermissionDenied, ParseError
from rest_framework.status import HTTP_201_CREATED
from rest_framework.permissions import DjangoModelPermissions

from common.verify import verify_max_length, verify_max_value, verify_in_array, verify_pk
from .models import Plan

import copy
# Create your views here.


class PlanEndpoint(APIView):
    permission_classes = (DjangoModelPermissions,)
    model = Plan
    queryset = model.objects.none()

    model_fields = [
        ('*name', str, (verify_max_length, 20)),
        ('*s_price', float, (verify_max_value, 1000)),
        ('*b_price', float, (verify_max_value, 1000)),
        ('*state', str, (verify_in_array, ('e', 'd'))),
        ('*offset', float, (verify_max_value, 2.0)),
        ('*plan_min_days', int, (verify_max_value, 365 * 6)),
        ('*offset_min_days', int, (verify_max_value, 365 * 6))
    ]

    model_pk = [
        ('*id', int, (verify_pk, model))
    ]

    def get(self, request):
        plan_id = request.GET.get('id', None)
        if plan_id:
            try:
                self.queryset = Plan.objects.filter(pk=plan_id)
            except ValueError:
                raise ParseError('id is not a number')
        else:
            self.queryset = Plan.objects.all()

        return Response({
            'code': 0,
            'msg': 'success',
            'data': self.queryset.values()
        })

    def post(self, request):
        # if not verify_super_user(request):
        #     raise PermissionDenied()
        print(self.model_fields)

        data = validate_post_data(request.body, tuple(self.model_fields))

        self.queryset, created = self.model.objects.update_or_create(**data)
        return Response({
            'code': 0,
            'msg': 'success',
            'data': self.queryset.json()
        }, status=HTTP_201_CREATED)

    def put(self, request):
        # if not verify_super_user(request):
        #     raise PermissionDenied()

        fields = copy.deepcopy(self.model_fields)
        fields.append(self.model_pk[0])
        data = validate_post_data(request.body, tuple(fields))

        self.queryset = self.model.objects.get(pk=data['id'])
        self.queryset.__dict__.update(**data)
        self.queryset.save()
        return Response({
            'code': 0,
            'msg': 'success',
        })

    def delete(self, request):
        # if not verify_super_user(request):
        #     raise PermissionDenied()

        # data = clean_post_data(request.body, tuple(self.model_pk))
        try:
            plan_id = request.GET.get('id', None)
            self.queryset = self.model.objects.get(pk=int(plan_id))
            self.queryset.delete()
        except (self.model.DoesNotExist, ValueError):
            raise ParseError('illegal id')
        return Response({
            'code': 0,
            'msg': 'success',
        })