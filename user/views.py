from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_201_CREATED, HTTP_403_FORBIDDEN
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from django.contrib.auth.models import User, AnonymousUser
from .models import Profile, Money
from django.db.models import Q
from django.forms.models import model_to_dict
from django.contrib.auth import authenticate, login, logout
from rest_framework.permissions import AllowAny, IsAdminUser
from common.verify import verify_field, verify_mail, verify_username, verify_phone, verify_body, verify_length, verify_max_length
from common.func import init_rgw_api
from django.core.paginator import Paginator
from django.conf import settings
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
        }, status=HTTP_400_BAD_REQUEST)

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
        ('*user_id', int, (verify_max_length, 10))
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
        rgw = init_rgw_api()
        try:
            if u.profile.is_subuser:
                rgw.remove_subuser(uid=u.profile.parent_uid, subuser=u.username, purge_keys=True)
            else:
                rgw.remove_user(uid=u.username, purge_data=True)
        except Exception as e:
            return Response({
                'code': 1,
                'msg': 'ceph radows remove user failed, ceph response mesage is %s' % e.args[0]
            }, status=HTTP_200_OK)
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
    if request.user.is_superuser:
        if username:
            users = User.objects.filter(
                Q(username=username) |
                Q(profile__parent_uid=username)
            )
        else:
            users = User.objects.all()
    else:
        username = request.user.username
        users = User.objects.filter(
            Q(username=username) |
            Q(profile__parent_uid=username)
        )

    buff = []
    for i in users:
        buff.append({
            'user_id': i.id,
            'first_name': i.first_name,
            'email': i.email,
            'phone': i.profile.phone,
            'is_active': i.is_active,
            'is_superuser': i.is_superuser,
            'date_joined': i.date_joined,
            'last_login': i.last_login,
            'username': i.username,
            'phone_verify': i.profile.phone_verify,
            'is_subuser': i.profile.is_subuser,
            'parent_uid': i.profile.parent_uid,
        })

    try:
        page_size = int(request.GET.get('page_size', settings.PAGE_SIZE))
        page = int(request.GET.get('page', 1))
    except:
        page_size = settings.PAGE_SIZE
        page = 1

    p = Paginator(buff, page_size)
    data = p.page(page)

    return Response({
        'code': 0,
        'msg': 'success',
        'data': list(data),
        'page_info': {
            'record_count': len(users),
            'page_size': page_size,
            'current_page': page
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
    try:
        u = User.objects.get(pk=user_id)
        # p = Profile.objects.get(user=u)
    except:
        return Response({
            'code': 1,
            'msg': 'error user id'
        }, status=HTTP_400_BAD_REQUEST)

    try:
        m = Money.objects.get(user=u)
    except:
        m = None
    req_username = request.user.username

    if not request.user.is_superuser and u.username != req_username and u.profile.parent_uid != req_username:
        return Response({
            'code': 1,
            'msg': 'permission denied'
        }, status=HTTP_403_FORBIDDEN)

    u_d = model_to_dict(u) if u else None
    p_d = model_to_dict(u.profile) if u else None
    m_d = model_to_dict(m) if m else None

    del u_d['password'], m_d['id'], p_d['id']
    return Response({
        'code': 0,
        'msg': 'success',
        'data': {
            'user': u_d,
            'profile': p_d,
            'money': m_d
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

    if user.profile.phone != data['phone']:
        return Response({
            'code': 1,
            'msg': 'phone error!',
        }, status=HTTP_400_BAD_REQUEST)

    rgw = init_rgw_api()
    try:
        if user.profile.is_subuser:
            rados_user = rgw.create_subuser(
                uid=user.profile.parent_uid,
                subuser=user.username,
                generate_secret=True,
            )
        else:
            rados_user = rgw.create_user(
                uid=user.username,
                display_name=user.first_name,
                generate_key=True,
                email=user.email,
                user_caps='usage=read; user=read,write; buckets=read,write',
                max_buckets=100
            )

        access_key = rados_user['keys'][0]['access_key']
        secret_key = rados_user['keys'][0]['secret_key']
        Profile.objects.filter(user=user).update(
            phone_verify=True,
            access_key=access_key,
            secret_key=secret_key
        )

    except Exception as e:
        return Response({
            'code': 1,
            'msg': 'radow create user failed, ceph response error %s' % e.args[0]
        })

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
        ('*money', float, (verify_max_length, 6))
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


@api_view(('GET',))
def GRANT_SUPERUSER_ENDPOINT(request):
    user = request.user
    u = User.objects.get(user=user)
    u.is_superuser = 1
    u.save()
    return Response({
        'msg': 'success'
    }, status=HTTP_200_OK)