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
from django.contrib.auth import authenticate, login, logout
from django.core.cache import cache

from requests.exceptions import ConnectionError, ReadTimeout

from buckets.models import BucketRegion, Buckets
from common.tokenauth import verify_permission
from common.verify import (
    verify_mail, verify_username,
    verify_phone, verify_length,
    verify_max_length, verify_phone_verification_code,
    verify_img_verification_code
)
from common.func import rgw_client, get_client_ip, validate_post_data
from .serializer import UserSerialize, UserDetailSerialize
from .models import Profile, DefaultGroup
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
        ('verify_code', str, verify_img_verification_code)
    )

    data = validate_post_data(request.body, fields)

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

    # 新注册用户加入默认用户角色
    try:
        dg = DefaultGroup.objects.get(default=True)
    except DefaultGroup.DoesNotExist:
        pass
    else:
        dg.group.user_set.add(user)

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

    data = validate_post_data(request.body, fields)
    # 因为用户名与手机号码均为唯一字段，所以一下条件只会有一个成立
    try:
        u = User.objects.select_related('profile').get(username=data['username'])
    except User.DoesNotExist:
        u = None

    try:
        p = Profile.objects.select_related('user').get(phone=data['username'])
    except Profile.DoesNotExist:
        p = None

    if not u and not p:
        raise NotFound('not found this user')

    user = None
    if u:
        user = u
    if p:
        user = p.user

    if not user.is_active:
        raise ParseError('user is inactive')

    if not authenticate(username=user.username, password=data['password']):
        raise ParseError('username or password is wrong')

    # if not verify_phone_verification_code(data['verify_code'], user.profile.phone):
    #     raise ParseError('phone verification code is wrong!')

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
        user.keys.init()

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


@api_view(('PUT',))
@verify_permission(model_name='user')
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

    data = validate_post_data(request.body, tuple(fields))

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
@verify_permission(model_name='user')
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
    data = validate_post_data(request.body, fields)

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
                rgw.get_user(uid=u.keys.ceph_uid, stats=True)
            except NoSuchUser:
                continue
            else:
                rgw.remove_user(uid=u.keys.ceph_uid, purge_data=True)
    u.delete()
    return Response({
        'code': 0,
        'msg': 'success'
    })


@api_view(('GET',))
@verify_permission(model_name='user')
def list_user_info_endpoint(request):
    """
    列出所有用户，当前操作对象为超级管理员时，可指定某个用户名，不批定则列出所有用户
    普通用户则列出自身帐户信息，以及所有子帐户信息
    :param request:
    :return:
    """
    username = request.GET.get('username', None)
    req_user = request.user

    users = User.objects. \
        select_related('profile'). \
        select_related('capacity_quota'). \
        select_related('bandwidth_quota'). \
        select_related('keys')

    if req_user.is_superuser:
        if username:
            user_list = users.filter(
                Q(username__contains=username) |
                Q(profile__parent_uid=username)
            )
        else:
            user_list = users.all()
    else:
        username = req_user.username
        user_list = users.filter(
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
    page.page_size = size
    page.number = cur_page
    page.max_page_size = 20
    ret = page.paginate_queryset(user_list.order_by('-id'), request)
    ser = UserSerialize(ret, many=True)
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
@verify_permission(model_name='user')
def get_user_detail_endpoint(request):
    """
    列出某个用户的所有详细信息
    超级管理员可以查看所有用户的信息，普通用户可以查看对应的子帐户信息
    :param request:
    :return:
    """
    try:
        user_id = request.GET.get('user_id', None)
        if not user_id:
            user_id = request.user.id

        u = User.objects. \
            select_related('profile'). \
            select_related('capacity_quota'). \
            select_related('bandwidth_quota'). \
            select_related('keys').get(id=user_id)
        b = Buckets.objects.filter(user=user_id).values('name')
    except Profile.DoesNotExist:
        raise ParseError(detail='not found user profile')
    except ValueError:
        raise ParseError(detail='user_id is not a number')

    if not request.user.is_superuser and \
            u != request.user and \
            u.profile.parent_uid != request.user.username and \
            u.profile.root_uid != request.user.username:
        raise NotAuthenticated()

    ser = UserDetailSerialize(u)
    ser_data = ser.data
    ser_data['bucket'] = [i['name'] for i in b]
    # ser_data['objects'] = {
    #     'count': Objects.objects.filter(owner=request.user, type='f').count()
    # }
    ser_data['real_usage'] = []
    region = BucketRegion.objects.all()

    for i in region:
        rgw = rgw_client(i.reg_id)
        try:
            x = rgw.get_user(uid=request.user.keys.ceph_uid, stats=True)
            ser_data['real_usage'].append({
                'region': i.name,
                'quota': x['user_quota'],
                'stats': x['stats']
            })
            # ser_data['ceph'][i.name]['stats'] = x
        except (ConnectionError, NoSuchUser, ReadTimeout):
            continue

    return Response({
        'code': 0,
        'msg': 'success',
        'data': ser_data
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
@verify_permission(model_name='user')
def query_user_usage(request):
    """
    查询用户流量及使情情况
    """
    req_user = request.user
    username = request.GET.get('username', None)
    start_time = request.GET.get('start', None)
    end_time = request.GET.get('end', None)

    fmt = '%F'

    u = User.objects.none()
    try:
        u = User.objects.get(username=username)
    except User.DoesNotExist:
        pass

    if not u:
        raise NotFound(detail='not fount this user')

    if u != req_user and not req_user.is_superuser:
        raise NotAuthenticated('permission denied!')

    if not start_time or not check_date_format(start_time):
        start_time = time.strftime(fmt, time.localtime(time.time() - 86400))

    if not end_time or not check_date_format(end_time):
        end_time = time.strftime(fmt, time.localtime())

    usage_data = []
    reg = BucketRegion.objects.all()
    for i in reg:
        rgw = rgw_client(i.reg_id)
        try:
            rgw.get_user(uid=req_user.keys.ceph_uid)
        except (NoSuchUser, ConnectionError):
            continue

        # print(start_time, end_time, u.profile.ceph_uid)
        def build_usage_data(origin_data):
            buff = {}
            for bucket in origin_data['entries'][0]['buckets']:
                act_time = bucket['time'][:10]
                buff[act_time] = {
                    'get_obj': {
                        'successful_ops': 0,
                        'bytes_sent': 0,
                    },
                    'put_obj': {
                        'successful_ops': 0,
                        'bytes_received': 0,
                    },
                }
                for cate in bucket['categories']:
                    if 'category' in cate and cate['category'] == 'put_obj':
                        buff[act_time]['put_obj']['successful_ops'] += cate['successful_ops']
                        buff[act_time]['put_obj']['bytes_received'] += cate['bytes_received']
                    if 'category' in cate and cate['category'] == 'get_obj':
                        buff[act_time]['get_obj']['successful_ops'] += cate['successful_ops']
                        buff[act_time]['get_obj']['bytes_sent'] += cate['bytes_sent']
            s_key = sorted(buff)
            __data = []
            for k in s_key:
                __tmp = {
                    'data': k
                }
                __tmp.update(buff[k])
                __data.append(__tmp)
                del __tmp
            return __data

        data = rgw.get_usage(
            uid=u.keys.ceph_uid,
            start=start_time,
            end=end_time,
            show_summary=True,
            show_entries=True
        )
        usage_data.append({
            'region': i.name,
            'usage_data': build_usage_data(data),
            'summary': data['summary']
        })

    return Response({
        'code': 0,
        'msg': 'success',
        'data': usage_data
    })


@api_view(('GET',))
def get_license_info_endpoint(request):
    return Response({
        'code': 0,
        'msg': 'success',
        'license': settings.LICENSE_INFO
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
    将请求用户的ip地址、ua、最新使用时间，结合token key写入缓存
    用户登陆时，使用cache中的信息校验
    """
    ua = request.META.get('HTTP_USER_AGENT', 'unknown')
    remote_ip = get_client_ip(request)
    user = Token.objects.get(key=token_key).user

    # write token extra info to cache
    cache.set('token_%s' % token_key, (ua, remote_ip, time.time(), user), 3600)
    # print(cache.get('token_%s' % token_key))
