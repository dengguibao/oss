from rest_framework.status import HTTP_201_CREATED
from rest_framework.exceptions import ParseError, NotFound, NotAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth.models import User, AnonymousUser
from django.conf import settings
from requests.exceptions import ConnectionError
from django.db.models import Q
from django.contrib.auth import authenticate, login, logout
from django.core.cache import cache
from buckets.models import BucketRegion, Buckets
from common.tokenauth import verify_permission
from common.verify import (
    verify_mail, verify_username,
    verify_phone, verify_length,
    verify_max_length, verify_max_value
)
from common.func import build_ceph_userinfo, rgw_client, get_client_ip, clean_post_data
from .serializer import UserSerialize, UserDetailSerialize
from .models import Profile, Money, Quota
from rgwadmin.exceptions import NoSuchUser

import time


@api_view(['POST'])
@permission_classes((AllowAny,))
def create_user_endpoint(request):
    """
    创建用户
    请求参数sub_user为1时则创建子用户
    创建子用户只能是一个已经登陆的普通用户
    :param request:
    :return:
    """
    try:
        sub_user = int(request.GET.get('sub_user', False))
    except ValueError:
        sub_user = 0

    sub_user = True if sub_user == 1 else False

    req_user = request.user

    if sub_user and isinstance(req_user, AnonymousUser):
        raise ParseError(detail='create sub user need a already exist user')

    if sub_user and not isinstance(req_user, AnonymousUser) and req_user.profile.level >= 3:
        raise ParseError('sub user already max level')

    fields = (
        ('*username', str, verify_username),
        ('*pwd', str, (verify_max_length, 30)),
        # ('*pwd2', str, None),
        ('*email', str, verify_mail),
        ('*first_name', str, (verify_max_length, 8)),
        ('*phone', str, verify_phone),
    )

    data = clean_post_data(request.body, fields)

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

        p = user.profile
        p.phone = data['phone']
        if sub_user:
            p.is_subuser = True
            p.parent_uid = request.user.username
            p.root_uid = request.user.profile.root_uid
            p.level = request.user.profile.level + 1
            p.save()
        p.save()

    except Exception as e:
        raise ParseError(detail=str(e))

    return Response({
        'code': 0,
        'msg': 'success'
    }, status=HTTP_201_CREATED)


@api_view(('POST',))
@permission_classes((AllowAny,))
def user_login_endpoint(request):
    """
    使用用户名和密码登陆
    """

    fields = (
        ('*username', str, verify_username),
        ('*password', str, (verify_max_length, 30)),
        ('*verify_code', str, (verify_length, 6))
    )

    data = clean_post_data(request.body, fields)

    try:
        u = User.objects.get(username=data['username'])
    except User.DoesNotExist:
        raise NotFound('not found this user')

    # -------------- login phone verify ------------
    # verify_code = cache.get('phone_verify_code_%s' % u.profile.phone)
    # if not verify_code:
    #     raise ParseError(detail='get phone verification code failed')
    #
    # if verify_code != data['verify_code']:
    #     raise ParseError(detail='phone verification code has wrong!')
    # cache.delete('phone_verify_code_%s' % u.profile.phone)
    # ------------- end ------------------
    user = authenticate(username=data['username'], password=data['password'])
    if not user or not user.is_active:
        raise ParseError(detail='username or password has wrong!')

    try:
        t = Token.objects.get(user=user)
        tk = t.key
        t.delete()
        cache.delete('token_%s' % tk)
    except Token.DoesNotExist:
        pass
    finally:
        tk, create = Token.objects.update_or_create(user=user)
        cache_request_user_meta_info(tk, request)

    # 首次登陆将生成access_key, secret_key, ceph_uid
    if not user.profile.phone_verify:
        uid, access_key, secret_key = build_ceph_userinfo(user.username)
        p = u.profile
        p.__dict__.update(
            **{
                'phone_verify': True,
                'access_key': access_key,
                'secret_key': secret_key,
                'ceph_uid': uid
            }
        )
        p.save()

    # 使用django login方法登陆，不然没有登陆记录，但是不需要任何session
    login(request, user=user)
    request.session.clear()
    logout(request)

    return Response({
        'code': 0,
        'msg': 'success',
        'data': {
            'token': tk.key,
            'user_id': user.pk,
            'username': user.username,
            'phone_verify': user.profile.phone_verify,
            'phone_number': user.profile.phone,
            'user_type': 'superuser' if user.is_superuser else 'normal',
            'is_subuser': user.profile.is_subuser,
            'level': user.profile.level,
        }
    })


@api_view(('POST',))
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
        fields.append(
            ('*old_pwd', str, (verify_max_length, 30))
        )

    data = clean_post_data(request.body, tuple(fields))

    # 验证两次密码是否一样
    if data['pwd1'] != data['pwd2']:
        raise ParseError(detail='the old and new password is not match!')
    # 超级管理员则查询指定的用户
    if request.user.is_superuser:
        try:
            user = User.objects.get(username=data['username'])
        except User.DoesNotExist:
            user = None
    else:
        user = request.user

    if user and user.username != data['username']:
        raise ParseError(detail='error username!')

    if request.user.is_superuser:
        user.set_password(data['pwd1'])

    if not request.user.is_superuser and authenticate(username=data['username'], password=data['old_pwd']):
        user.set_password(data['pwd1'])
    else:
        raise ParseError('old password is error!')

    user.save()

    return Response({
        'code': 0,
        'msg': 'success'
    })


@api_view(('DELETE',))
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
    data = clean_post_data(request.body, fields)

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
# @verify_permission(model_name='user')
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
        users = User.objects.select_related('profile').select_related('quota').filter(
            Q(username=username) |
            Q(profile__parent_uid=username) |
            Q(profile__root_uid=username)
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
    :return:
    """
    # u = User.objects.get(pk=user_id)

    try:
        user_id = request.GET.get('user_id', None)
        u = User.objects.select_related('profile').select_related('quota').select_related('money').get(id=user_id)
        b = Buckets.objects.filter(user=user_id).values()
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

    # u_d = model_to_dict(u)
    # p_d = model_to_dict(p)
    # m_d = model_to_dict(m)
    #
    # del u_d['password'], m_d['id'], p_d['id']

    ser = UserDetailSerialize(u)
    ser_data = ser.data
    ser_data['bucket'] = b
    # ser_data['objects'] = {
    #     'count': Objects.objects.filter(owner=request.user, type='f').count()
    # }
    ser_data['ceph'] = []
    region = BucketRegion.objects.all()

    for i in region:
        rgw = rgw_client(i.reg_id)
        try:
            x = rgw.get_user(uid=request.user.profile.ceph_uid, stats=True)
            ser_data['ceph'].append({
                'region': i.name,
                'quota': x['user_quota'],
                'stats': x['stats']
            })
            # ser_data['ceph'][i.name]['stats'] = x
        except ConnectionError:
            continue
        except NoSuchUser:
            continue

    return Response({
        'code': 0,
        'msg': 'success',
        'data': ser_data
    })


@api_view(('POST',))
@permission_classes((AllowAny,))
def user_charge_endpoint(request):
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
    data = clean_post_data(request.body, fields)

    m = req_user.money.get()
    m.charge(data['money'])

    return Response({
        'code': 0,
        'msg': 'success',
        'amount': m.amount
    })


@api_view(("GET",))
@permission_classes((AllowAny,))
def query_user_exist_endpoint(request):
    """
    根据查询条件查询用户是否
    """
    username = request.GET.get('username', None)
    phone = request.GET.get('phone', None)
    email = request.GET.get('email', None)

    if not username and not phone and not email:
        exist = 'unknown'
    else:
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
        else:
            exist = True

    return Response({
        'code': 0,
        'msg': 'success',
        'exist': exist
    })


@api_view(("GET",))
@permission_classes((AllowAny,))
def query_user_usage(request):
    """
    查询用户流量及使情情况
    """
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
        start_time = time.strftime(fmt, time.localtime(time.time() - 86400))

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
        except ConnectionError:
            continue
        # print(start_time, end_time, u.profile.ceph_uid)
        data = rgw.get_usage(
            uid=u.profile.ceph_uid,
            start=start_time,
            end=end_time,
            show_summary=True,
            # show_entries=True
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
def set_capacity_endpoint(request):
    """
    设置或者修改用户存储容量，即用户配额
    """
    fields = [
        # 最大购买40T流量
        ('*capacity', int, (verify_max_value, 40960)),
        # 最大购买时长1年
        ('*duration', int, (verify_max_value, 365))
    ]

    data = clean_post_data(request.data, tuple(fields))

    if request.method == 'POST':
        q, created = Quota.objects.update_or_create(user=request.user)

    if request.method == 'PUT':
        q = Quota.objects.get(user=request.user)

    if data['capacity'] < q.capacity:
        raise ParseError('original capacity big than select capacity')

    q.renewal(data['duration'], data['capacity'])
    return Response({
        'code': 0,
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
    cache.set('token_%s' % token_key, (ua, remote_ip, time.time(), user), 3600)
    # print(cache.get('token_%s' % token_key))
