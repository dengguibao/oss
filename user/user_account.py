from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from common.func import validate_post_data
from common.verify import verify_length, verify_max_value


@api_view(('POST',))
@permission_classes((AllowAny,))
def user_recharge_endpoint(request):
    """
    用户充值
    :param request:
    :return:
    """
    req_user = request.user

    fields = (
        ('*order_id', str, (verify_length, 10)),
        ('*money', float, (verify_max_value, 99999.0))
    )
    data = validate_post_data(request.body, fields)

    p = req_user.profile.get()
    p.charge(data['money'])

    return Response({
        'code': 0,
        'msg': 'success',
        'balance': p.balance
    })