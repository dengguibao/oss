from rgwadmin import RGWAdmin
from boto3.session import Session
from django.conf import settings
from objects.models import Objects
from buckets.models import BucketRegion
from django.contrib.auth.models import User
import random
import os
import uuid

def init_rgw_api():
    access_key, secret_key, server = settings.RGW_API_KEY['NORMAL']
    return RGWAdmin(
        access_key=access_key,
        secret_key=secret_key,
        server=server,
        secure=False,
        verify=False
    )


def init_s3_connection(access_key, secret_key):
    _, _, server = settings.RGW_API_KEY['NORMAL']
    conn = Session(aws_access_key_id=access_key, aws_secret_access_key=secret_key)
    client = conn.client(
        service_name='s3',
        endpoint_url='http://%s' % server,
        verify=False
    )
    return client


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
    except:
        return False
    else:
        return obj


def build_tmp_filename():
    rand_str = ''.join(random.sample('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', 10))
    file_name = '/tmp/ceph_oss_%s.dat' % rand_str
    return file_name


def rgw_client(region_id: int):
    try:
        b = BucketRegion.objects.get(reg_id=region_id)
    except:
        return

    return RGWAdmin(
        access_key=b.access_key,
        secret_key=b.secret_key,
        server=b.server,
        secure=False,
        verify=False
    )


def s3_client(reg_id: int, username: str):
    u = User.objects.get(username=username)
    if not u.profile.phone_verify:
        return
    region = BucketRegion.objects.get(reg_id=reg_id)
    rgw = rgw_client(reg_id)
    try:
        rgw.get_user(uid=u.profile.ceph_uid)
    except:
        rgw.create_user(
            uid=u.profile.ceph_uid,
            access_key=u.profile.access_key,
            secret_key=u.profile.secret_key,
            display_name=u.first_name,
            max_buckets=200,
            user_caps='buckets=read,write;user=read,write;usage=read'
        )
        rgw.set_user_quota(uid=u.profile.ceph_uid, max_size_kb=u.traffic.capacity*1024**2)
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
    x = str(uuid.uuid3(uuid.NAMESPACE_DNS, username)).replace('-', '')
    secret_key = str(uuid.uuid4()).replace('-', '')

    uid = random_build_str(x, 8)
    access_key = random_build_str(x, 24)
    return uid, access_key, secret_key


def random_build_str(origin_str: str, uid_len: int) -> str:
    """
    随机构建key
    """
    if len(origin_str) < 32:
        return str(uuid.uuid1()).replace('-', '')[:uid_len]
    data = []
    for i in range(uid_len):
        x = random.randint(0, 31)
        if x < 15:
            data.append(origin_str[x].upper())
        else:
            data.append(origin_str[x])

    return ''.join(data)


def get_client_ip(request):
    """
    获取客户端ip地址
    """
    try:
        remote_ip = request.META['HTTP_X_FORWARDED_FOR'].split(',')[0]
    except KeyError:
        remote_ip = request.META.get('REMOTE_ADDR', None)
    return remote_ip
