from rgwadmin import RGWAdmin
from boto3.session import Session
from rest_framework.exceptions import ParseError, PermissionDenied
from common.verify import verify_field
from objects.models import Objects
from buckets.models import BucketRegion
from django.contrib.auth.models import User
from django.conf import Settings
from rgwadmin.exceptions import NoSuchUser
from hashlib import md5
import random
import os
# import uuid
import requests
from oss import get_clock

from oss import settings


def file_iter(filename):
    """
    使用流式下载文件是，分批读取文件流
    """
    if not os.path.exists(filename) or not os.path.isfile(filename):
        return
    with open(filename, 'rb') as fp:
        while 1:
            d = fp.read(4096)
            if d:
                yield d
            else:
                break
    os.remove(filename)


def verify_path(path: str, bucket_name: str):
    """
    查询用户post过来的路径是否为真实有效已存在的路径
    """
    if not path or path.startswith('/') and not path.endswith('/'):
        return False
    try:
        obj = Objects.objects.select_related("bucket").get(key=path, type='d', bucket__name=bucket_name)
    except Objects.DoesNotExist:
        return False
    else:
        return True


# def build_tmp_filename():
#     """
#     随机生成一个临时文件名
#     """
#     file_name = '/tmp/ceph_oss_%s.dat' % random_build_str(10)
#     return file_name


def rgw_client(region_id: int):
    """
    初始化rgw客户端

    使用区域中的管理员key生成rgw客户端
    """
    try:
        b = BucketRegion.objects.get(reg_id=region_id)
    except BucketRegion.DoesNotExist:
        return

    return RGWAdmin(
        access_key=b.access_key,
        secret_key=b.secret_key,
        server=b.server[7:] if b.server.startswith('http://') else b.server[8:],
        secure=False if b.server.startswith('http://') else True,
        verify=False,
        timeout=5,
    )


def s3_client(reg_id: int, username: str):
    """
    初始化s3客户端

    使用指定区域中的管理员key查询用户是否存在
    如果用户存在则使用用户的key创建s3客户端
    如果不存在则创建该用户，使用指定的key，然后再初始化s3客户端
    """
    region = BucketRegion.objects.get(reg_id=reg_id)
    u = User.objects.select_related('profile'). \
        select_related('capacity_quota'). \
        select_related('keys').get(username=username)
    if not u.profile.phone_verify:
        return

    if region.type == 'local':
        rgw = rgw_client(reg_id)

        try:
            ceph_user = rgw.get_user(uid=u.keys.ceph_uid)
        except NoSuchUser:
            ceph_user = rgw.create_user(
                uid=u.keys.ceph_uid,
                access_key=u.keys.ceph_access_key,
                secret_key=u.keys.ceph_secret_key,
                display_name=u.first_name,
                max_buckets=200,
                user_caps='buckets=read,write;user=read,write;usage=read'
            )
        except Exception as e:
            msg = e.args[0]
            settings.LOGGER.error(msg)
            raise ParseError(msg)

        assert ceph_user, ParseError("ceph create user failed")

        user_quota = ceph_user['user_quota']
        if user_quota['enabled'] is not True or user_quota['max_size_kb'] != u.capacity_quota.capacity*1024**2:
            rgw.set_user_quota(
                uid=u.keys.ceph_uid,
                max_size_kb=u.capacity_quota.capacity*1024**2,
                enabled=True,
                quota_type='user'
            )
            u.capacity_quota.ceph_sync()

        conn = Session(
            aws_access_key_id=u.keys.ceph_access_key,
            aws_secret_access_key=u.keys.ceph_secret_key
        )

        client = conn.client(
            service_name='s3',
            endpoint_url=region.server,
            verify=False
        )
        return client

    if region.type == 'amazon':
        conn = Session(
            aws_access_key_id=region.access_key,
            aws_secret_access_key=region.secret_key
        )

        client = conn.client(
            service_name='s3',
            endpoint_url=region.server,
            verify=False
        )
        return client


def build_ceph_userinfo() -> tuple:
    """
    根据用户名构建ceph_uid, access_key, secret_key
    """
    # x = str(uuid.uuid3(uuid.NAMESPACE_DNS, username)).replace('-', '')
    secret_key = random_build_str(40)
    uid = random_build_str(8)
    access_key = random_build_str(24)
    return uid, access_key, secret_key


def random_build_str(length: int) -> str:
    """
    随机构建生成指定长度的字符串，包含a-zA-Z0-9
    """
    return ''.join(random.sample('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', length))


def get_client_ip(request):
    """
    获取客户端ip地址
    """
    try:
        remote_ip = request.META['HTTP_X_FORWARDED_FOR'].split(',')[0]
    except KeyError:
        remote_ip = request.META.get('REMOTE_ADDR', None)
    return remote_ip


def send_phone_verify_code(phone: str):
    """
    利用短信接口，向指定的手机号码发送验证码短信
    """
    sn = 'SDK-BBX-010-37896'
    pwd = 'ihEb64rQ'
    mix_pwd = '%s%s' % (sn, pwd)
    mobile = phone
    verify_code = ''.join(random.sample('0123456789', 6))
    ret = requests.post(
        'http://sdk.entinfo.cn:8061/mdsmssend.ashx',
        headers={
            'Content-Type': 'application/x-www-form-urlencoded'
        },
        data={
            'sn': sn,
            'pwd': md5(mix_pwd.encode()).hexdigest().upper(),
            'mobile': mobile,
            'content': '【FuRongCloud】芙蓉云对象存储短信验证码为：%s，切勿将验证码泄露于他人，本条验证码有效期2分钟。' % verify_code
        }
    )
    return ret.status_code, verify_code


def validate_post_data(body_data, fields):
    """
    过滤与验证用户的请求数据
    """
    data = verify_field(body_data, tuple(fields))
    if data and not isinstance(data, dict):
        raise ParseError(data)
    else:
        return data


def verify_super_user(request):
    """
    验证用户是否为超级管理员
    """
    if not request.user.is_superuser:
        raise PermissionDenied('only allow super user access')


def validate_license_expire():
    # print(get_clock(), settings.LICENSE_INFO['end_time'])
    c = get_clock()
    if c <= 0 or c > settings.LICENSE_INFO['end_time']:
        raise ParseError('license is expired!')