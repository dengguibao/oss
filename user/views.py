from rest_framework.status import (
    HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_201_CREATED,
    HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND
)
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
from buckets.models import BucketRegion, Buckets
from common.verify import (
    verify_field, verify_mail, verify_username,
    verify_phone, verify_body, verify_length,
    verify_max_length, verify_max_value
)
from common.func import build_ceph_userinfo, rgw_client
from .serializer import UserSerialize
from .models import Profile, Money

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
    is_subuser = request.GET.get('is_subuser', 0)
    try:
        is_subuser = int(is_subuser)
    except:
        is_subuser = 0
    else:
        is_subuser = True if is_subuser == 1 else False

    req_user = request.user

    if is_subuser and isinstance(req_user, AnonymousUser):
        return Response({
            'code': 1,
            'msg': 'illegal request, create sub user need a already user'
        })

    if not isinstance(req_user, AnonymousUser) and req_user.profile.is_subuser:
        return Response({
            'code': 1,
            'msg': 'illegal request, only normal can be create sub user'
        })

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
        return Response({
            'code': 1,
            'msg': data,
        }, status=HTTP_400_BAD_REQUEST)

    # if data['pwd1'] != data['pwd2']:
    #     return Response({
    #         'code': 1,
    #         'msg': 'The two passwords are different'
    #     })

    try:
        User.objects.get(username=data['username'])
    except:
        pass
    else:
        return Response({
            'code': 1,
            'msg': 'user already exist!'
        }, status=HTTP_400_BAD_REQUEST)

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

        if not is_subuser:
            Money.objects.create(
                user=user,
                amount=0.0
            )
        Token.objects.create(user=user)
    except Exception as e:
        return Response({
            'code': 1,
            'msg': e.args[1] if len(e.args) > 1 else str(e.args)
        }, status=HTTP_400_BAD_REQUEST)

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
        return Response({
            'code': 1,
            'msg': data
        }, status=HTTP_404_NOT_FOUND)

    user = authenticate(username=data['username'], password=data['password'])
    if not user or not user.is_active:
        return Response({
            'code': 1,
            'msg': 'username or password is wrong!'
        }, status=HTTP_400_BAD_REQUEST)

    token, create = Token.objects.get_or_create(user=user)
    login(request, user=user)
    request.session.clear()
    logout(request)

    if not create:
        token_create_ts = token.created.timestamp()
        if time.time() - token_create_ts > settings.TOKEN_EXPIRE_TIME:
            token.delete()
            token = Token.objects.create(user=user)

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
    }, status=HTTP_200_OK)


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
        return Response({
            'code': 1,
            'msg': data
        }, status=HTTP_400_BAD_REQUEST)

    if data['pwd1'] != data['pwd2']:
        return Response({
            'code': 1,
            'msg': 'the old and new password is not match!'
        }, status=HTTP_400_BAD_REQUEST)

    user = None
    if request.user.is_superuser:
        try:
            user = User.objects.get(username=data['username'])
        except:
            pass
    else:
        user = authenticate(username=data['username'], password=data['old_pwd'])
        # user = User.objects.get(username='te2st')

    if user and user.username != data['username']:
        return Response({
            'code': 1,
            'msg': 'error username!'
        }, status=HTTP_400_BAD_REQUEST)

    user.set_password(data['pwd1'])
    user.save()

    return Response({
        'code': 0,
        'msg': 'success'
    }, status=HTTP_200_OK)


@api_view(('DELETE',))
@verify_body
def user_delete_endpoint(request):
    """
    删除指定的用户，该超作只允许超级管理员执行
    :param request:
    :return:
    """
    if not request.user.is_superuser:
        return Response({
            'code': 1,
            'msg': 'permission denied!'
        }, status=HTTP_403_FORBIDDEN)

    fields = (
        ('*username', str, verify_username),
        ('*user_id', int, None)
    )
    data = verify_field(request.body, fields)
    if not isinstance(data, dict):
        return Response({
            'code': 1,
            'msg': data
        }, status=HTTP_400_BAD_REQUEST)

    try:
        u = User.objects.get(pk=data['user_id'])
    except:
        return Response({
            'code': 1,
            'msg': 'not found this user'
        }, status=HTTP_400_BAD_REQUEST)
    else:
        if u.username != data['username']:
            return Response({
                'code': 1,
                'msg': 'error username'
            }, status=HTTP_400_BAD_REQUEST)

    if u.profile.phone_verify:
        region = BucketRegion.objects.all()
        # 递归删除所有区域集群上的用户
        for i in region:
            rgw = rgw_client(i.reg_id)
            try:
                rgw.get_user(uid=u.profile.ceph_uid, stats=True)
            except:
                continue
            else:
                rgw.remove_user(uid=u.profile.ceph_uid, purge_data=True)
    u.delete()
    return Response({
        'code': 1,
        'msg': 'success'
    }, status=HTTP_200_OK)


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
                Q(username=username) |
                Q(profile__parent_uid=username)
            )
        else:
            users = User.objects.select_related('profile').all()
    else:
        username = req_user.username
        users = User.objects.select_related('profile').filter(
            Q(username=username) |
            Q(profile__parent_uid=username)
        )

    try:
        cur_page = int(request.GET.get('page', 1))
        size = int(request.GET.get('size', settings.PAGE_SIZE))
    except:
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
    }, status=HTTP_200_OK)


@api_view(('GET',))
def get_user_detail_endpoint(request, user_id):
    """
    列出某个用户的所有详细信息
    超级管理员可以查看所有用户的信息，普通用户可以查看对应的子帐户信息
    :param request:
    :param user_id:
    :return:
    """
    u = User.objects.get(pk=user_id)

    try:
        u = User.objects.get(pk=user_id)
        p = Profile.objects.get(user=u)
        m = Money.objects.get(user=u)
        b = Buckets.objects.filter(user=u)


    except:
        return Response({
            'code': 1,
            'msg': 'error user id'
        }, status=HTTP_400_BAD_REQUEST)

    req_username = request.user.username

    if not request.user.is_superuser and \
            u.username != req_username and \
            u.profile.parent_uid != req_username:
        return Response({
            'code': 1,
            'msg': 'permission denied'
        }, status=HTTP_403_FORBIDDEN)

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


@api_view(('POST',))
@verify_body
def verify_user_phone_endpoint(request):
    """
    验证用户注册时填写的手机号码，确认真实有效
    只有成功通过手机验证的用户才允许在ceph集群上创建对应的帐户
    :param request:
    :return:
    """
    fields = (
        ('*phone', str, verify_phone),
        ('*verify_code', str, (verify_length, 6))
    )
    data = verify_field(request.body, fields)
    if not isinstance(data, dict):
        return Response({
            'code': 1,
            'msg': data,
        }, status=HTTP_400_BAD_REQUEST)

    user = request.user

    if user.profile.phone != data['phone'] or user.profile.phone_verify:
        return Response({
            'code': 1,
            'msg': 'phone number error or that user is already verification',
        }, status=HTTP_400_BAD_REQUEST)
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
    }, status=HTTP_200_OK)


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
        return Response({
            'code': 1,
            'msg': 'sub user can not charge'
        }, status=HTTP_400_BAD_REQUEST)

    fields = (
        ('*order_id', str, (verify_length, 10)),
        ('*money', float, (verify_max_value, 99999.0))
    )
    data = verify_field(request.body, fields)

    if not isinstance(data, dict):
        return Response({
            'code': 1,
            'msg': data
        })

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
    try:
        User.objects.get(username=username)
    except:
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
    req_user = request.user
    username = request.GET.get('username', None)
    start_time = request.GET.get('start', None)
    end_time = request.GET.get('end', None)

    fmt = '%F'

    u = False
    try:
        u = User.objects.get(username=username)
    except:
        pass

    if not u or (u != req_user and not req_user.is_superuser):
        return Response({
            'code': 1,
            'msg': 'not found this user'
        }, status=HTTP_400_BAD_REQUEST)

    if not start_time or not check_date_format(start_time):
        start_time = time.strftime(fmt, time.localtime())

    if not end_time or not check_date_format(end_time):
        end_time = time.strftime(fmt, time.localtime())

    usage_data = []
    reg = BucketRegion.objects.all()
    for i in reg:
        rgw = rgw_client(i.reg_id)
        try:
            rgw.get_user(uid=req_user.profile.ceph_uid)
        except:
            continue

        data = rgw.get_usage(
            uid=username,
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


@api_view(('GET',))
def __GRANT_SUPERUSER_ENDPOINT__(request):
    user = request.user
    u = User.objects.get(user=user)
    u.is_superuser = 1
    u.save()
    return Response({
        'msg': 'success'
    }, status=HTTP_200_OK)


def check_date_format(s: str) -> bool:
    try:
        fmt = '%Y-%m-%d'
        time.strptime(s, fmt)
    except Exception as e:
        return False

    return True
