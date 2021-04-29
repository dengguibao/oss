from django.conf import settings
from rest_framework.exceptions import ParseError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import DjangoModelPermissions

from account.models import Plan
from common.func import clean_post_data
from common.verify import verify_max_value, verify_number_range, verify_pk
from user.models import CapacityQuota, BandwidthQuota
from .signal import create_order


class CapacityQuotaEndpoint(APIView):
    permission_classes = (DjangoModelPermissions,)
    model = CapacityQuota
    queryset = model.objects.none()

    duration_field = ('*duration', int, (verify_max_value, 365 * 5))
    value_field = ('*capacity', int, (verify_max_value, 40960))
    plan_field = ('*plan_id', int, (verify_pk, Plan))

    def get(self, request):
        self.queryset = self.model.objects.get(user=request.user)
        return Response({
            'code': 0,
            'msg': 'success',
            'data': self.queryset.json
        })

    def post(self, request):
        fields = (
            self.plan_field,
            self.duration_field,
            self.value_field
        )
        force = request.GET.get('force', None)
        data = clean_post_data(request.data, fields)

        self.queryset = self.model.objects.get(user=request.user)

        if force is None:
            if self.queryset.valid():
                raise ParseError('not deadline')

        if data['capacity'] < self.queryset.capacity:
            raise ParseError('original capacity big than new capacity')

        total, offset_total = self.calculate_cost(
            request.user,
            data['capacity'],
            data['duration'],
            data['plan_id'],
            'storage'
        )

        result = self.queryset.renewal(data['duration'], data['capacity'])

        request.user.profile.cost(offset_total)
        create_order.send(
            self.put,
            product='s',
            detail="capacity: %s, duration:%s" % (data['capacity'], data['duration']),
            user_id=request.user.id,
            pay=total,
            real_pay=offset_total,
            plan_id=data['plan_id']
        )

        return Response({
            'code': 0,
            'msg': 'success',
            'data': result
        })

    def put(self, request):
        fields = (
            self.duration_field,
            self.plan_field
        )
        data = clean_post_data(request.data, fields)
        self.queryset = self.model.objects.get(user=request.user)

        total, offset_total = self.calculate_cost(
            request.user,
            self.queryset.capacity,
            data['duration'],
            data['plan_id'],
            'storage'
        )
        result = self.queryset.renewal(data['duration'], self.queryset.capacity)
        request.user.profile.cost(offset_total)
        create_order.send(
            self.put,
            product='s',
            detail="capacity: %s, duration:%s" % (data['capacity'], data['duration']),
            user_id=request.user.id,
            pay=total,
            real_pay=offset_total,
            plan_id=data['plan_id']
        )
        return Response({
            'code': 0,
            'msg': 'success',
            'data': result
        })

    def calculate_cost(self, user, size: int, duration: int, plan_id: int, type: str):
        plan = Plan.objects.get(pk=int(plan_id))
        if plan.state != 'e':
            raise ParseError('illegal plan')

        if duration < plan.plan_min_days:
            raise ParseError('duration less plan mini days')

        offset = plan.offset if duration >= plan.offset_min_days else 1.0

        if type == 'storage':
            price = plan.s_price

        if type == 'bandwidth':
            price = plan.b_price

        total = (size*duration*price)/365
        offset_total = total*offset

        if user.profile.balance < offset_total:
            raise ParseError('account of balance not enough')

        return round(total, 2), round(offset_total, 2)


class BandwidthQuotaEndpoint(CapacityQuotaEndpoint):
    model = BandwidthQuota
    value_field = ('*bandwidth', int, (verify_number_range, (settings.USER_MIN_BANDWIDTH, 1024)))

    def post(self, request):
        fields = (
            self.duration_field,
            self.value_field,
            self.plan_field
        )
        force = request.GET.get('force', None)
        data = clean_post_data(request.data, fields)

        self.queryset = self.model.objects.get(user=request.user)

        if force is None:
            if self.queryset.valid():
                raise ParseError('not deadline')

        if data['bandwidth'] < self.queryset.bandwidth:
            raise ParseError('original bandwidth big than new bandwidth')

        total, offset_total = self.calculate_cost(
            request.user,
            self.queryset.bandwidth,
            data['duration'],
            data['plan_id'],
            'bandwidth'
        )

        result = self.queryset.renewal(data['duration'], data['bandwidth'])
        request.user.profile.cost(offset_total)
        create_order.send(
            self.put,
            product='b',
            detail="bandwidth: %s, duration:%s" % (data['bandwidth'], data['duration']),
            user_id=request.user.id,
            pay=total,
            real_pay=offset_total,
            plan_id=data['plan_id']
        )
        return Response({
            'code': 0,
            'msg': 'success',
            'data': result
        })

    def put(self, request):
        fields = (
            self.plan_field,
            self.duration_field,
        )
        data = clean_post_data(request.data, fields)
        self.queryset = self.model.objects.get(user=request.user)

        total, offset_total = self.calculate_cost(
            request.user,
            self.queryset.bandwidth,
            data['duration'],
            data['plan_id'],
            'bandwidth'
        )

        result = self.queryset.renewal(data['duration'], self.queryset.bandwidth)
        request.user.profile.cost(offset_total)
        create_order.send(
            self.put,
            product='b',
            detail="bandwidth: %s, duration:%s" % (data['bandwidth'], data['duration']),
            user_id=request.user.id,
            pay=total,
            real_pay=offset_total,
            plan_id=data['plan_id']
        )
        return Response({
            'code': 0,
            'msg': 'success',
            'data': result
        })
