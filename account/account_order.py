from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination

from .serialize import OrderSerialize

from account.models import Order


class OrderEndpoint(APIView):
    model = Order
    queryset = model.objects.none()

    def get(self, request):
        obj = Order.objects.select_related('user').select_related('plan')
        order_no = request.GET.get('order_no', None)
        if order_no:
            data = obj.filter(no=order_no)
            if data and request.user.is_superuser is not None:
                data = data.filter(user=request.user)
        else:
            data = obj.all() if request.user.is_superuser else obj.filter(user=request.user)

        self.queryset = data.order_by('-id')

        try:
            cur_page = int(request.GET.get('page', 1))
            size = int(request.GET.get('size', settings.PAGE_SIZE))
        except ValueError:
            cur_page = 1
            size = settings.PAGE_SIZE

        page = PageNumberPagination()
        page.page_size = size
        page.number = cur_page
        page.max_page_size = 20
        ret = page.paginate_queryset(self.queryset, request)
        ser = OrderSerialize(ret, many=True)

        return Response({
            'code': 0,
            'msg': 'success',
            'data': ser.data,
            'page_info': {
                'record_count': len(ser.data),
                'page_size': size,
                'current_page': page.page.number
            }
        })
