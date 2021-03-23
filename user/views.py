from rest_framework import status
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from django.contrib.auth.models import User
from .models import Profile
import json
from django.contrib.auth import authenticate, login, logout
import time
from rest_framework.permissions import AllowAny, IsAdminUser
from common.verify import verify_field, verify_mail, verify_username, verify_phone
from django.core.paginator import Paginator
from django.conf import settings


@api_view(['POST'])
@permission_classes((AllowAny, ))
def create_user_endpoint(request):
    try:
        j = json.loads(request.body.decode())
    except:
        return Response({
            'code': 1,
            'msg': 'illegal request, body format error'
        }, status=status.HTTP_400_BAD_REQUEST)

    fields = (
        ('*username', str, verify_username),
        ('*pwd', str, None),
        # ('*pwd2', str, None),
        ('*email', str, verify_mail),
        ('*first_name', str, None),
        ('*phone', str, verify_phone),
    )

    data = verify_field(j, fields)

    if not isinstance(data, dict):
        return Response({
            'code': 1,
            'msg': data,
        }, status=status.HTTP_400_BAD_REQUEST)

    # if data['pwd1'] != data['pwd2']:
    #     return Response({
    #         'code': 1,
    #         'msg': 'The two passwords are different'
    #     })

    try:
        tmp = User.objects.get(username=data['username'])
    except:
        pass
    else:
        return Response({
            'code': 1,
            'msg': 'user already exist!'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.create_user(
            username=data['username'],
            password=data['pwd'],
            email=data['email'],
            first_name=data['first_name'],
        )
        Profile.objects.update_or_create(
            user=user,
            phone=data['phone']
        )
        Token.objects.create(user=user)
    except Exception as e:
        return Response({
            'code': 1,
            'msg': e.args[1] if len(e.args) > 1 else str(e.args)
        }, status=status.HTTP_400_BAD_REQUEST)
    else:
        return Response({
            'code': 0,
            'msg': 'success'
        }, status=status.HTTP_201_CREATED)


@api_view(('POST',))
@permission_classes((AllowAny, ))
def user_login_endpoint(request):
    """
    user login
    """
    try:
        j = json.loads(request.body.decode())
    except:
        return Response({
            'code': 1,
            'msg': 'illegal request, body format error'
        }, status=status.HTTP_400_BAD_REQUEST)

    fields = (
        ('*username', str, verify_username),
        ('*password', str, None)
    )

    data = verify_field(j, fields)
    if not isinstance(data, dict):
        return Response({
            'code': 1,
            'msg': data
        }, status=status.HTTP_400_BAD_REQUEST)

    user = authenticate(username=data['username'], password=data['password'])
    if not user or not user.is_active:
        return Response({
            'code': 1,
            'msg': 'username or password is wrong!'
        }, status=status.HTTP_400_BAD_REQUEST)

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
            'user_type': 'superuser' if user.is_superuser else 'normal'
        }
    }, status=status.HTTP_200_OK)


@api_view(('POST',))
def change_password_endpoint(request):
    """
    if request.user is superuser then change the password of specified user, else change the password is user itself
    """
    try:
        j = json.loads(request.body.decode())
    except:
        return Response({
            'code': 1,
            'msg': 'illegal request, body format error'
        }, status=status.HTTP_400_BAD_REQUEST)

    fields = [
        ('*username', str, verify_username),
        ('*pwd1', str, None),
        ('*pwd2', str, None),
    ]

    if not request.user.is_superuser:
        fields = [
            ('*username', str, verify_username),
            ('*old_pwd', str, None),
            ('*pwd1', str, None),
            ('*pwd2', str, None),
        ]

    data = verify_field(j, tuple(fields))

    if not isinstance(data, dict):
        return Response({
            'code': 1,
            'msg': data
        }, status=status.HTTP_400_BAD_REQUEST)

    if data['pwd1'] != data['pwd2']:
        return Response({
            'code': 1,
            'msg': 'the old and new password is not match!'
        }, status=status.HTTP_400_BAD_REQUEST)

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
        }, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(data['pwd1'])
    user.save()

    return Response({
        'code': 0,
        'msg': 'success'
    }, status=status.HTTP_200_OK)


@api_view(('DELETE',))
@permission_classes((IsAdminUser,))
def user_delete_endpoint(request):
    if not request.user.is_superuser:
        return Response({
            'code': 1,
            'msg': 'permission denied!'
        }, status=status.HTTP_403_FORBIDDEN)
    try:
        j = json.loads(request.body.decode())
    except:
        return Response({
            'code': 1,
            'msg': 'illegal request, body format error'
        }, status=status.HTTP_400_BAD_REQUEST)

    fields = (
        ('*username', str, verify_username),
        ('*user_id', int, None)
    )
    data = verify_field(j, fields)
    if not isinstance(data, dict):
        return Response({
            'code': 1,
            'msg': data
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        u = User.objects.get(pk=data['user_id'])
    except:
        return Response({
            'code': 1,
            'msg': 'not found this user'
        }, status=status.HTTP_400_BAD_REQUEST)
    else:
        if u.username != data['username']:
            return Response({
                'code': 1,
                'msg': 'error username'
            }, status=status.HTTP_400_BAD_REQUEST)

    u.delete()
    return Response({
        'code': 1,
        'msg': 'success'
    }, status=status.HTTP_200_OK)


@api_view(('GET',))
def list_user_info_endpoint(request):
    if request.user.is_superuser:
        username = request.GET.get('username', None)
        if username:
            users = User.objects.filter(username=username)
        else:
            users = User.objects.all()
    else:
        users = [request.user]

    buff = []
    for i in users:
        buff.append({
            'id': i.id,
            'first_name': i.first_name,
            'email': i.email,
            'phone': i.profile.phone,
            'is_active': i.is_active,
            'is_superuser': i.is_superuser,
            'date_joined': i.date_joined,
            'last_login': i.last_login,
            'username': i.username,
            'phone_verify': i.profile.phone_verify
        })

    try:
        page_size = int(request.GET.get('page_size', 10))
        page = int(request.GET.get('page', 1))
    except:
        page_size = 10
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
    }, status=status.HTTP_200_OK)

