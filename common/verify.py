import re
import json
from django.db.models import Model
from django.core.cache import cache


def verify_phone(phone: str) -> bool:
    """
    验证手机号码是否为真实
    """
    try:
        int(phone)
    except ValueError:
        return False

    support_phone_prefix = ['13', '14', '15', '16', '17', '18', '19']

    return False if len(phone) != 11 or phone[0:2] not in support_phone_prefix else True


def verify_is_equal(x, y):
    """
    verify two object whether equal
    """
    return True if x == y else False


def verify_field(data: bytes, fields: tuple):
    """
    使用用户自定义的函数验证用户传过来的数据
    字段格式为（字段名，字段类型，验证方法）， 其中字段名，第一个字符为*的为段包含在字典中的key
    验证方法可以为元组，如果为元组，则第一个元素为验证方法，第二个元素为验证方法的参数
    -----------
    例如：
    fields = (
        ('*name', str, (verify_max_length, 10))
    )
    以上字段会验证json中的name是否为字符串，则最大长度不能超过10个字符
    -----------
    通过则返回包含字段中的key的字典，否则返回未验证通过的信息
    """

    # 防止过大的非法post数据包
    if len(data) > 2*1024**2:
        return 'json body is too large'

    if isinstance(data, (str, bytes, bytearray)):
        try:
            data = json.loads(data)
        except json.decoder.JSONDecodeError:
            return 'request body is not a json'
    elif isinstance(data, dict):
        pass
    else:
        return 'illegal request body'

    buff = dict()

    # 防止所有字段都为可选字段，但是组合起来必须有一项目
    pass_flag = False

    assert isinstance(fields, tuple), 'fields format has wrong!'

    for field_name, field_type, verify_param in fields:
        # 以*开头的为必选段段

        if field_name[0] == '*':
            field_name = field_name[1:]
            if field_name not in data or \
                    (isinstance(data[field_name], bool) and data[field_name] not in (True, False)) or \
                    (isinstance(data[field_name], str) and len(data[field_name].strip()) == 0):
                return 'field "%s" is necessary and value can not be empty' % field_name

        if field_name not in data:
            continue

        # 验证数据类型
        if not isinstance(data[field_name], field_type):
            return 'field %s type wrong!' % field_name

        verify_result = False
        # 自定义校验函数，且提供两个参数
        if isinstance(verify_param, tuple) and len(verify_param) > 1:
            verify_func = verify_param[0]
            verify_arg = verify_param[1]
            verify_result = verify_func(data[field_name], verify_arg)

        # 自定义检验函数， 只提供一个参数
        if hasattr(verify_param, '__call__'):
            verify_result = verify_param(data[field_name])

        if not verify_result:
            return 'field %s verify failed!' % field_name

        # 防止所有参数均为可选，但是全部加起来有必选一项
        if field_name in data:
            pass_flag = True

    if pass_flag:
        for k, _, _ in fields:
            if k[0] == '*':
                k = k[1:]

            if k in data:
                # 如果是文本内容最多只接收200个字符
                if isinstance(data[k], str):
                    data[k] = data[k].strip()[0:1024]
                buff[k] = data[k]
        return buff
    return False


def verify_mail(mail: str) -> bool:
    """
    verify mail whether invalid
    """
    return True if re.match("^.+@(\\[?)[a-zA-Z0-9\\-.]+\\.([a-zA-Z]{2,3}|[0-9]{1,3})(]?)$", mail) else False


def verify_username(username: str) -> bool:
    """
    正则验证用户名
    """
    return True if re.match("^[A-Z0-9a-z_\\-.]{6,20}$", username) else False


def verify_bucket_name(name: str) -> bool:
    """
    正则验证bucket名称
    """
    return True if re.match('^[a-z0-9][a-z0-9\\-]{1,62}$', name) else False


def verify_length(data: str, length: int) -> bool:
    """
    验证长度
    """
    return True if len(data) == length else False


def verify_in_array(data: str, array: tuple) -> bool:
    """
    验证元素是否包含在指定的元组中
    """
    return True if data in array else False


def verify_true_false(i) -> bool:
    """
    验证对象是否为真、假、1、0
    """
    return True if i in ('1', 1, 'true', 'false', 0, '0') else False


def verify_max_length(s: str, max_len: int) -> bool:
    """
    验证最大允许长度
    """
    return True if len(s) < max_len else False


def verify_max_value(i, max_value) -> bool:
    """
    验证数字的最大值
    """
    return True if 0 < i < max_value else False


def verify_number_range(value: int, num_range: tuple):
    """
    验证数字是否在某个范围内
    """
    x, y = num_range
    return True if x < value < y else False


def verify_pk(i: int, model: Model) -> bool:
    """
    验证某个对象的的主键是否为真实有效
    """
    try:
        model.objects.get(pk=int(i))
    except model.DoesNotExist:
        return False
    return True


def verify_object_name(value: str) -> bool:
    """
    验证上传文件对象的文件名是否合法
    """
    return True if re.match('^[\u4e00-\u9fa5a-zA-Z0-9\\-_]{1,1024}$', value) else False


def verify_object_path(value: str) -> bool:
    """
    验证对象路径是否为有合法
    """
    # 路径不能用/开头但是必须以/结尾
    if not value.endswith('/') or value.startswith('/'):
        return False
    if not re.match('^[\u4e00-\u9fa5a-zA-Z0-9,\\-_/]{1,2048}/$', value):
        return False
    return True


def verify_phone_verification_code(value: str, phone: str) -> bool:
    """
    验证用户输入的手机验证码是否正确
    """
    if not verify_length(value, 6):
        return False

    cached_verification_code = cache.get('phone_verify_code_%s' % phone)
    if not cached_verification_code:
        return False

    if value != cached_verification_code:
        return False

    cache.delete('phone_verify_code_%s' % phone)
    return True


def verify_img_verification_code(value: str) -> bool:
    """
    验证图形验证码是否正确
    """
    if not verify_length(value, 5):
        return False
    cached_verification_code = cache.get('img_verify_code_%s' % value.upper())
    if not cached_verification_code:
        return False
    cache.delete('img_verify_code_%s' % value.upper())
    return True


def verify_ip_addr(ip: str) -> bool:
    """
    verify ip whether is a invalid ip
    :param ip:
    :return:
    """
    if len(ip) > 15 or '.' not in ip or len(ip.split('.')) > 4:
        return False
    first = True
    for i in ip.split('.'):
        try:
            n = int(i)
        except ValueError:
            return False
        if n > 255:
            return False
        if first and n == 0 and ip != '0.0.0.0':
            return False
        first = False
    return True


def verify_url(value: str):
    return True if value.startswith('http://') or value.startswith('https://') else False


# def verify_body(func):
#     def wrap(request, *args, **kwargs):
#         if request.method in ('DELETE', 'POST', 'PUT'):
#             try:
#                 j = json.loads(request.body.decode())
#             except:
#                 return Response({
#                     'code': 1,
#                     'msg': 'illegal request, request content is not application/json'
#                 }, status=HTTP_400_BAD_REQUEST)
#         return func(request, *args, **kwargs)
#     return wrap
