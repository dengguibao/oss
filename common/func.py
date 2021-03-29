from rgwadmin import RGWAdmin
from boto3.session import Session
from django.conf import settings
from objects.models import Objects
import random
import os


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
    # 利用模型的name和root联合匹配
    # e.g.
    #     aaa/bbb/ccc/
    #     root:aaa/bbb/ sub_dir_name: ccc/
    # ['aaa', 'bbb', 'ccc', '']
    if not path or path.startswith('/') and not path.endswith('/'):
        return False
    try:
        obj = Objects.objects.select_related("bucket")
        a = path.split('/')
        if len(a) > 2:
            # ccc/
            sub_dir_name = a[-2] + '/'
            del a[-2]
            # aaa/bbb/
            root_name = '/'.join(a)
            return obj.get(name=sub_dir_name, root=root_name, type='d')

        # 只有一层目录则只用查询名称
        # aaa/  ['aaa', '']
        if len(a) == 2:
            return obj.get(name=path, type='d')
    except:
        return False


def build_tmp_filename():
    rand_str = ''.join(random.sample('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', 10))
    file_name = '/tmp/ceph_oss_%s.dat' % rand_str
    return file_name