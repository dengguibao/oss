from rest_framework.status import HTTP_201_CREATED
from rest_framework.exceptions import ParseError, NotFound, NotAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth.models import User, AnonymousUser
from django.conf import settings
from django.db.models import Q
from django.forms.models import model_to_dict
from django.contrib.auth import authenticate, login, logout
from django.core.cache import cache
from buckets.models import BucketRegion, Buckets
from common.verify import (
    verify_field, verify_mail, verify_username,
    verify_phone, verify_body, verify_length,
    verify_max_length, verify_max_value, verify_pk
)
from common.func import build_ceph_userinfo, rgw_client, get_client_ip, send_phone_verify_code
from .serializer import UserSerialize
from .models import Profile, Money, Capacity
from rgwadmin.exceptions import NoSuchUser

import time


@api_view(['POST'])
@permission_classes((AllowAny,))
@verify_body
def create_user_endpoint(request):
    """
    创建用户
    请求参数is_subuser为1时则创建子用户
    创建子用户只能是一个已经登陆的普通用户
    :param request:
    :return:
    """
    try:
        is_subuser = int(request.GET.get('is_subuser', 0))
    except ValueError:
        is_subuser = 0

    is_subuser = True if is_subuser == 1 else False

    req_user = request.user

    if is_subuser and isinstance(req_user, AnonymousUser):
        raise ParseError(detail='create sub user need a already exist user')

    # if not isinstance(req_user, AnonymousUser) and not request.user.profile.is_subuser:
    #     raise ParseError(detail='illegal request, only normal user can be create sub user')

    fields = (
        ('*username', str, verify_username),
        ('*pwd', str, (verify_max_length, 30)),
        # ('*pwd2', str, None),
        ('*email', str, verify_mail),
        ('*first_name', str, (verify_max_length, 8)),
        ('*phone', str, verify_phone),
    )

    data = verify_field(request.body, fields)

    if not isinstance(data, dict):
        raise ParseError(detail=data)

    # if data['pwd1'] != data['pwd2']:
    #     return Response({
    #         'code': 1,
    #         'msg': 'The two passwords are different'
    #     })

    try:
        User.objects.get(username=data['username'])
    except User.DoesNotExist:
        pass
    else:
        raise ParseError(detail='the user is already exist')

    try:
        User.objects.get(email=data['email'])
    except User.DoesNotExist:
        pass
    else:
        raise ParseError(detail='the email is already exist')

    try:
        Profile.objects.get(phone=data['phone'])
    except Profile.DoesNotExist:
        pass
    else:
        raise ParseError(detail='the phone number already exist')

    try:
        user = User.objects.create_user(
            username=data['username'],
            password=data['pwd'],
            email=data['email'],
            first_name=data['first_name'],
        )

        p, created = Profile.objects.update_or_create(
            user=user,
            phone=data['phone']
        )
        if is_subuser:
            p.is_subuser = True
            p.parent_uid = request.user.username
            p.save()

        # if not is_subuser:
        Money.objects.create(
            user=user,
            amount=0.0
        )
        Token.objects.create(user=user)
    except Exception as e:
        raise ParseError(detail=str(e))

    return Response({
        'code': 0,
        'msg': 'success'
    }, status=HTTP_201_CREATED)


@api_view(('POST',))
@permission_classes((AllowAny,))
@verify_body
def user_login_endpoint(request):
    """
    使用用户名和密码登陆，成功登陆获取token，当token超过setting.TOKEN_EXPIRE_TIME后更新token
    """

    fields = (
        ('*username', str, verify_username),
        ('*password', str, (verify_max_length, 30))
    )

    data = verify_field(request.body, fields)
    if not isinstance(data, dict):
        raise ParseError(detail=data)

    user = authenticate(username=data['username'], password=data['password'])
    if not user or not user.is_active:
        raise ParseError(detail='username or password has wrong!')

    try:
        Token.objects.get(user=user).delete()
    except Token.DoesNotExist:
        pass

    token, create = Token.objects.update_or_create(user=user)
    cache_request_user_meta_info(token, request)
    # 使用django login方法登陆，不然没有登陆记录，但是不需要任何session
    login(request, user=user)
    request.session.clear()
    logout(request)

    return Response({
        'code': 0,
        'msg': 'success',
        'data': {
            'token': token.key,
            'user_id': user.pk,
            'username': user.username,
            'phone_verify': user.profile.phone_verify,
            'phone_number': user.profile.phone,
            'user_type': 'superuser' if user.is_superuser else 'normal',
        }
    })


@api_view(('POST',))
@verify_body
def change_password_endpoint(request):
    """
    修改用户名密码，如果是超级管理员则不需要提供原密码，直接更改某个用户的密码
    普通用户更改密码需要提供原始密码和新密码
    """

    fields = [
        ('*username', str, verify_username),
        ('*pwd1', str, (verify_max_length, 30)),
        ('*pwd2', str, (verify_max_length, 30)),
    ]

    if not request.user.is_superuser:
        fields = [
            ('*username', str, verify_username),
            ('*old_pwd', str, (verify_max_length, 30)),
            ('*pwd1', str, (verify_max_length, 30)),
            ('*pwd2', str, (verify_max_length, 30)),
        ]

    data = verify_field(request.body, tuple(fields))

    if not isinstance(data, dict):
        raise ParseError(detail=data)

    if data['pwd1'] != data['pwd2']:
        raise ParseError(detail='the old and new password is not match!')

    user = None
    if request.user.is_superuser:
        try:
            user = User.objects.get(username=data['username'])
        except User.DoesNotExist:
            pass
    else:
        user = authenticate(username=data['username'], password=data['old_pwd'])
        # user = User.objects.get(username='te2st')

    if user and user.username != data['username']:
        raise ParseError(detail='error username!')

    user.set_password(data['pwd1'])
    user.save()

    return Response({
        'code': 0,
        'msg': 'success'
    })


@api_view(('DELETE',))
@verify_body
def user_delete_endpoint(request):
    """
    删除指定的用户，该超作只允许超级管理员执行
    :param request:
    :return:
    """
    # if not request.user.is_superuser:
    #     raise NotAuthenticated(detail='permission denied!')

    fields = (
        ('*username', str, verify_username),
        ('*user_id', int, None)
    )
    data = verify_field(request.body, fields)
    if not isinstance(data, dict):
        raise ParseError(detail=data)

    try:
        u = User.objects.get(pk=data['user_id'])
    except User.DoesNotExist:
        raise NotFound(detail='not found this user')

    if not request.user.is_superuser and u != request.user:
        raise NotAuthenticated(detail='permission denied')

    if u.username != data['username']:
        raise ParseError(detail='username and user_id not match')

    if u.profile.phone_verify:
        region = BucketRegion.objects.all()
        # 递归删除所有区域集群上的用户
        for i in region:
            rgw = rgw_client(i.reg_id)
            try:
                rgw.get_user(uid=u.profile.ceph_uid, stats=True)
            except NoSuchUser:
                continue
            else:
                rgw.remove_user(uid=u.profile.ceph_uid, purge_data=True)
    u.delete()
    return Response({
        'code': 1,
        'msg': 'success'
    })


@api_view(('GET',))
def list_user_info_endpoint(request):
    """
    列出所有用户，当前操作对象为超级管理员时，可指定某个用户名，不批定则列出所有用户
    普通用户则列出自身帐户信息，以及所有子帐户信息
    :param request:
    :return:
    """
    username = request.GET.get('username', None)
    req_user = request.user
    if req_user.is_superuser:
        if username:
            users = User.objects.filter(
                Q(username__contains=username) |
                Q(profile__parent_uid=username)
            )
        else:
            users = User.objects.select_related('profile').all()
    else:
        username = req_user.username
        users = User.objects.select_related('profile').select_related('capacity').filter(
            Q(username=username) |
            Q(profile__parent_uid=username)
        )

    try:
        cur_page = int(request.GET.get('page', 1))
        size = int(request.GET.get('size', settings.PAGE_SIZE))
    except ValueError:
        cur_page = 1
        size = settings.PAGE_SIZE

    page = PageNumberPagination()
    # page.page_query_param = 'page'
    # page.page_size_query_param = 'size'

    page.page_size = size
    page.number = cur_page
    page.max_page_size = 20

    ret = page.paginate_queryset(users.order_by('-id'), request)
    ser = UserSerialize(ret, many=True)
    # print(page.page_size, page.page_size)
    return Response({
        'code': 0,
        'msg': 'success',
        'data': ser.data,
        'page_info': {
            'record_count': len(users),
            'page_size': size,
            'current_page': page.page.number
        }
    })


@api_view(('GET',))
def get_user_detail_endpoint(request):
    """
    列出某个用户的所有详细信息
    超级管理员可以查看所有用户的信息，普通用户可以查看对应的子帐户信息
    :param request:
    :param user_id:
    :return:
    """
    # u = User.objects.get(pk=user_id)

    try:
        user_id = request.GET.get('user_id', None)
        if int(user_id):
            u = User.objects.get(pk=user_id)
            p = Profile.objects.get(user=u)
            m = Money.objects.get(user=u)
            b = Buckets.objects.filter(user=u)
    except Profile.DoesNotExist:
        raise ParseError(detail='not found user profile')
    except Money.DoesNotExist:
        raise ParseError(detail='not found money object')
    except ValueError:
        raise ParseError(detail='user_id is not a number')

    req_username = request.user.username

    if not request.user.is_superuser and \
            u.username != req_username and \
            u.profile.parent_uid != req_username:
        raise NotAuthenticated(detail='permission denied!')

    u_d = model_to_dict(u)
    p_d = model_to_dict(p)
    m_d = model_to_dict(m)

    del u_d['password'], m_d['id'], p_d['id']
    return Response({
        'code': 0,
        'msg': 'success',
        'data': {
            'user': u_d,
            'profile': p_d,
            'money': m_d,
            'bucket': list(b.values())
        }
    })


@api_view(('POST', 'GET',))
@verify_body
def verify_user_phone_endpoint(request):
    """
    验证用户注册时填写的手机号码，确认真实有效
    只有成功通过手机验证的用户才允许在ceph集群上创建对应的帐户
    :param request:
    :return:
    """
    if request.method == 'GET':
        if not cache.get('phone_verify_code_%s' % request.user.profile.phone):
            status_code, verify_code = send_phone_verify_code(request.user.profile.phone)

            if status_code == 200:
                cache.set('phone_verify_code_%s' % request.user.profile.phone, verify_code, 900)
        else:
            raise ParseError(detail='verification code already send')

        return Response({
            'code': 0,
            'msg': 'success'
        })

    if request.method == 'POST':
        fields = (
            ('*phone', str, verify_phone),
            ('*verify_code', str, (verify_length, 6))
        )
        data = verify_field(request.body, fields)
        if not isinstance(data, dict):
            raise ParseError(detail=data)

        user = request.user

        if user.profile.phone != data['phone'] or user.profile.phone_verify:
            raise ParseError(detail='phone number error or that user is already verification')

        verify_code = cache.get('phone_verify_code_%s' % user.profile.phone)
        if not verify_code or data['verify_code'] != verify_code:
            raise ParseError(detail='verification code error')

        cache.delete('phone_verify_code_%s' % user.profile.phone)
        uid, access_key, secret_key = build_ceph_userinfo(user.username)
        # print(uid,access_key,secret_key)
        p = Profile.objects.get(user=user)
        p.__dict__.update(
            **{
                'phone_verify': True,
                'access_key': access_key,
                'secret_key': secret_key,
                'ceph_uid': uid
            }
        )
        p.save()
        return Response({
            'code': 0,
            'msg': 'success',
        })


@api_view(('POST',))
@verify_body
def user_charge_endpoint(request):
    """
    用户充值，只允许普通用户用户充值，子帐户不允许充值
    :param request:
    :return:
    """
    req_user = request.user
    if req_user.profile.is_subuser:
        raise NotAuthenticated(detail='sub user can not charge')

    fields = (
        ('*order_id', str, (verify_length, 10)),
        ('*money', float, (verify_max_value, 99999.0))
    )
    data = verify_field(request.body, fields)

    if not isinstance(data, dict):
        raise ParseError(detail=data)

    user_money = Money.objects.get(user=req_user)
    user_money.charge(data['money'])
    current = user_money.amount

    return Response({
        'code': 0,
        'msg': 'success',
        'amount': current
    })


@api_view(("GET",))
@permission_classes((AllowAny,))
def query_user_exist_endpoint(request):
    username = request.GET.get('username', None)
    phone = request.GET.get('phone', None)
    email = request.GET.get('email', None)

    exist = True
    try:
        if username:
            User.objects.get(username=username)

        if phone:
            Profile.objects.get(phone=phone)

        if email:
            User.objects.get(email=email)
    except User.DoesNotExist:
        exist = False
    except User.MultipleObjectsReturned:
        exist = True
    except Profile.DoesNotExist:
        exist = False

    return Response({
        'code': 0,
        'msg': 'success',
        'exist': exist
    })


@api_view(("GET",))
@permission_classes((AllowAny,))
def query_user_usage(request):
    req_user = request.user
    username = request.GET.get('username', None)
    start_time = request.GET.get('start', None)
    end_time = request.GET.get('end', None)

    fmt = '%F'

    u = False
    try:
        u = User.objects.get(username=username)
    except User.DoesNotExist:
        pass

    if not u or (u != req_user and not req_user.is_superuser):
        raise NotFound(detail='not fount this user')

    if not start_time or not check_date_format(start_time):
        start_time = time.strftime(fmt, time.localtime(time.time()-86400))

    if not end_time or not check_date_format(end_time):
        end_time = time.strftime(fmt, time.localtime())

    usage_data = []
    reg = BucketRegion.objects.all()
    for i in reg:
        rgw = rgw_client(i.reg_id)
        try:
            rgw.get_user(uid=req_user.profile.ceph_uid)
        except NoSuchUser:
            continue
        # print(start_time, end_time, u.profile.ceph_uid)
        data = rgw.get_usage(
            uid=u.profile.ceph_uid,
            start=start_time,
            end=end_time,
            show_summary=True,
            show_entries=True
        )
        usage_data.append({
            'region': i.name,
            'usage_data': data
        })

    return Response({
        'code': 0,
        'msg': 'success',
        'data': usage_data
    })


@api_view(('POST', 'PUT'))
@verify_body
def set_capacity_endpoint(request):
    fields = [
        # 最大购买40T流量
        ('*capacity', int, (verify_max_value, 40960)),
        # 最大购买时长1年
        ('*duration', int, (verify_max_value, 365))
    ]
    if request.method == 'PUT':
        fields.append(
            ('*c_id', int, (verify_pk, Capacity))
        )

    data = verify_field(request.data, tuple(fields))
    if not isinstance(data, dict):
        raise ParseError(detail=data)

    if request.method == 'POST':
        t, created = Capacity.objects.update_or_create(user=request.user)

    if request.method == 'PUT':
        t = Capacity.objects.get(c_id=data['c_id'])

    t.renewal(data['duration'], data['capacity'])
    return Response({
        'code': 0,
        'msg': 'success'
    })


@api_view(('GET',))
def __GRANT_SUPERUSER_ENDPOINT__(request):
    user = request.user
    u = User.objects.get(user=user)
    u.is_superuser = 1
    u.save()
    return Response({
        'msg': 'success'
    })


def check_date_format(s: str) -> bool:
    try:
        fmt = '%Y-%m-%d'
        time.strptime(s, fmt)
    except ValueError:
        return False

    return True


def cache_request_user_meta_info(token_key, request):
    """
    将请求用户的ip地址、ua、最新使用时间，结合中token key写入缓存
    用户登陆时，使用cache中的信息校验
    """
    ua = request.META.get('HTTP_USER_AGENT', 'unknown')
    remote_ip = get_client_ip(request)
    user = Token.objects.get(key=token_key).user

    # write token extra info to cache
    cache.set('token_%s' % token_key, (ua, remote_ip, time.time(), user))
    # print(cache.get('token_%s' % token_key))
