from rgwadmin import RGWAdmin
from boto3.session import Session
from rest_framework.exceptions import ParseError, PermissionDenied
from common.verify import verify_field
from objects.models import Objects
from buckets.models import BucketRegion
from django.contrib.auth.models import User
from rgwadmin.exceptions import NoSuchUser
from hashlib import md5
import random
import os
# import uuid
import requests


def file_iter(filename):
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


def verify_path(path):
    # 判断用户传过来的路程径是否为真实有效
    if not path or path.startswith('/') and not path.endswith('/'):
        return False
    try:
        obj = Objects.objects.select_related("bucket").get(key=path, type='d')
    except Objects.DoesNotExist:
        return False
    else:
        return obj


def build_tmp_filename():
    file_name = '/tmp/ceph_oss_%s.dat' % random_build_str(10)
    return file_name


def rgw_client(region_id: int):
    try:
        b = BucketRegion.objects.get(reg_id=region_id)
    except BucketRegion.DoesNotExist:
        return

    return RGWAdmin(
        access_key=b.access_key,
        secret_key=b.secret_key,
        server=b.server,
        secure=False,
        verify=False
    )


def s3_client(reg_id: int, username: str):
    u = User.objects.select_related('profile').select_related('quota').get(username=username)
    if not u.profile.phone_verify:
        return
    region = BucketRegion.objects.get(reg_id=reg_id)
    rgw = rgw_client(reg_id)
    try:
        rgw.get_user(uid=u.profile.ceph_uid)
    except NoSuchUser:
        rgw.create_user(
            uid=u.profile.ceph_uid,
            access_key=u.profile.access_key,
            secret_key=u.profile.secret_key,
            display_name=u.first_name,
            max_buckets=200,
            user_caps='buckets=read,write;user=read,write;usage=read'
        )
    rgw.set_user_quota(uid=u.profile.ceph_uid, max_size_kb=u.quota.capacity*1024**2, enabled=True, quota_type='user')
    conn = Session(
        aws_access_key_id=u.profile.access_key,
        aws_secret_access_key=u.profile.secret_key
    )
    client = conn.client(
        service_name='s3',
        endpoint_url='http://%s' % region.server,
        verify=False
    )
    return client


def build_ceph_userinfo(username: str) -> tuple:
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
    随机构建key
    """
    return ''.join(random.sample('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', length))
    # if len(origin_str) < 32:
    #     return str(uuid.uuid1()).replace('-', '')[:uid_len]
    # data = []
    # for i in range(uid_len):
    #     x = random.randint(0, 31)
    #     if x < 15:
    #         data.append(origin_str[x].upper())
    #     else:
    #         data.append(origin_str[x])
    #
    # return ''.join(data)


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


def clean_post_data(body_data, fields):
    data = verify_field(body_data, tuple(fields))
    if not isinstance(data, dict):
        raise ParseError(data)
    else:
        return data


def verify_super_user(request):
    if not request.user.is_superuser:
        raise PermissionDenied('only allow super user access')
