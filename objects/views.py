from rest_framework.status import (
    HTTP_200_OK, HTTP_201_CREATED, HTTP_404_NOT_FOUND,
    HTTP_400_BAD_REQUEST, HTTP_403_FORBIDDEN
)
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import api_view
from django.conf import settings
from django.http.response import Http404
from django.http import StreamingHttpResponse
from buckets.models import Buckets

from common.verify import (
    verify_body, verify_pk, verify_object_name,
    verify_field, verify_object_path, verify_bucket_name
)
from common.func import init_s3_connection
from .serializer import ObjectsSerialize
from .models import Objects
import random
import hashlib
import os


@api_view(('POST',))
@verify_body
def create_directory_endpoint(request):
    req_user = request.user
    _fields = (
        ('*bucket_name', str, verify_bucket_name),
        ('*folder_name', str, verify_object_name),
        ('path', str, verify_object_path)
    )
    data = verify_field(request.body, _fields)
    if not isinstance(data, dict):
        return Response({
            'code': 1,
            'msg': data
        }, status=HTTP_400_BAD_REQUEST)

    b = Buckets.objects.get(name=data['bucket_name'])
    if req_user.id != b.user_id:
        return Response({
            'code': 2,
            'msg': 'illegal request, error bucket name'
        })

    access_key = req_user.profile.access_key
    secret_key = req_user.profile.secret_key
    if not access_key or not secret_key:
        return Response({
            'code': 3,
            'msg': 'not found access_key or secret_key'
        })

    try:
        if 'path' in data:
            # 验证目录是否在正确的bucket下面
            p = None
            p = verify_path(data['path'])
            if not p or p.owner != req_user or p.bucket.name != data['bucket_name']:
                return Response({
                    'code': 1,
                    'msg': 'path error'
                }, status=HTTP_400_BAD_REQUEST)

            key = data['path']+data['folder_name']+'/'
        else:
            key = data['folder_name']+'/'

        s3 = init_s3_connection(access_key, secret_key)
        d = s3.put_object(Bucket=b.name, Body=b'', Key=key)

        Objects.objects.create(
            name=data['folder_name']+'/',
            bucket=b,
            etag=d['ETag'] if 'ETag' in d else None,
            version_id=d['VersionId'] if 'VersionId' in d else None,
            type='d',
            key=key,
            root=data['path'] if 'path' in data else None,
            owner=req_user
        )
    except Exception as e:
        return Response({
            'code': 4,
            'msg': 'create folder failed',
            'error': '%s' % str(e)
        })

    return Response({
        'code': 0,
        'msg': 'success'
    })


@api_view(('DELETE',))
def delete_object_endpoint(request):
    req_user = request.user
    try:
        obj_id = request.GET.get('obj_id', 0)
        o = Objects.objects.get(obj_id=int(obj_id))
    except:
        return Response({
            'code': 1,
            'msg': 'not found this object resource'
        }, status=HTTP_404_NOT_FOUND)

    if o.owner != req_user:
        return Response({
            'code': 1,
            'msg': 'permission denied!'
        }, status=HTTP_403_FORBIDDEN)

    access_key = req_user.profile.access_key
    secret_key = req_user.profile.secret_key
    try:
        s3 = init_s3_connection(access_key, secret_key)
        delete_list = []
        if o.type == 'd':
            root_pth = '' if o.root is None else o.root
            obj_name = o.name
            key = root_pth+obj_name
            delete_list.append(
                (o.obj_id, o.key)
            )
            for i in Objects.objects.filter(root__startswith=key, owner=req_user).all():
                delete_list.append(
                    (i.obj_id, i.key)
                )
        if o.type == 'f':
            delete_list.append(
                (o.obj_id, o.key)
            )

        for del_id, del_key in delete_list:
            s3.delete_object(
                Bucket=o.bucket.name,
                Key=del_key
            )
            Objects.objects.get(obj_id=del_id).delete()

    except Exception as e:
        return Response({
            'code': 3,
            'msg': 'delete object failed',
            'error': '%s' % str(e)
        })

    return Response({
        'code': 0,
        'msg': 'success'
    })


@api_view(('GET',))
def list_objects_endpoint(request):
    req_user = request.user
    path = request.GET.get('path', None)
    bucket_name = request.GET.get('bucket_name', None)
    try:
        err = False
        b = Buckets.objects.get(name=bucket_name)
    except:
        err = True
    if err or b.user != req_user:
        return Response({
            'code': 1,
            'msg': 'not found this bucket'
        })
    res = Objects.objects.select_related('bucket').select_related('owner').filter(owner=req_user, bucket=b)
    if path:
        res = res.filter(root=path.replace(',', '/'))
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
    # page.page_size = size
    page.number = cur_page
    page.max_page_size = 20
    ret = page.paginate_queryset(res, request)
    ser = ObjectsSerialize(ret, many=True)
    return Response({
        'code': 0,
        'msg': 'success',
        'data': ser.data
    })


@api_view(('PUT',))
def put_object_endpoint(request):
    req_user = request.user
    bucket_name = request.POST.get('bucket_name', None)
    # filename = request.POST.get('filename', None)
    file = request.FILES.get('file', None)
    path = request.POST.get('path', None)

    if not file:
        return Response({
            'code': 1,
            'msg': 'no upload file'
        }, status=HTTP_400_BAD_REQUEST)

    filename = file.name
    err = True
    if not bucket_name:
        pass
    try:
        b = Buckets.objects.get(user=req_user, name=bucket_name)
    except:
        pass
    else:
        err = False

    if err:
        return Response({
            'code': 1,
            'msg': 'not found this bucket'
        })

    p = None
    if path and not path.startswith('/') and path.endswith('/'):
        p = verify_path(path)

    if p and p.owner != req_user and p.bucket.name != bucket_name:
        return Response({
            'code': 1,
            'msg': 'path error'
        }, status=HTTP_400_BAD_REQUEST)

    if len(filename) > 63:
        return Response({
            'code': 1,
            'msg': 'filename to long'
        }, status=HTTP_400_BAD_REQUEST)

    temp_file = build_tmp_filename()

    md5 = hashlib.md5()
    with open(temp_file, 'wb') as f:
        for chunk in file.chunks():
            md5.update(chunk)
            f.write(chunk)

    access_key = req_user.profile.access_key
    secret_key = req_user.profile.secret_key
    if not access_key or not secret_key:
        return Response({
            'code': 2,
            'msg': 'not found access_key or secret_key'
        })

    try:
        s3 = init_s3_connection(access_key, secret_key)

        if p and p.root:
            root = p.root+p.name
        else:
            root = ''

        # 利用s3接口进行数据上传至rgw
        mp = s3.create_multipart_upload(Bucket=b.name, Key=root+filename)
        with open(temp_file, 'rb') as fp:
            n = 1
            parts = []
            while True:
                data = fp.read(5*1024**2)
                if not data:
                    break
                x = s3.upload_part(
                    Body=data,
                    Bucket=b.name,
                    ContentLength=len(data),
                    Key=root+filename,
                    UploadId=mp['UploadId'],
                    PartNumber=n
                )
                parts.append({
                    'ETag': x['ETag'].replace('"', ''),
                    'PartNumber': n
                })
                n += 1

            d = s3.complete_multipart_upload(
                Bucket=b.name,
                Key=root+filename,
                UploadId=mp['UploadId'],
                MultipartUpload={'Parts': parts}
            )

        # 创建或更新数据库
        Objects.objects.update_or_create(
            name=filename,
            bucket=b,
            type='f',
            root=root,
            file_size=file.size,
            key=root+filename,
            md5=md5.hexdigest(),
            etag=d['ETag'] if 'ETag' in d else None,
            owner=req_user
        )
        # 删除临时文件
        os.remove(temp_file)

    except Exception as e:
        return Response({
            'code': 3,
            'msg': 'put object failed',
            'err': str(e)
        }, status=HTTP_400_BAD_REQUEST)

    return Response({
        'code': 0,
        'msg': 'success'
    })


@api_view(('GET',))
def download_object_endpoint(request):
    req_user = request.user
    try:
        obj_id = int(request.GET.get('obj_id', None))
        obj = Objects.objects.select_related("bucket").get(obj_id=obj_id)
    except:
        pass

    if (obj and obj.owner != req_user) or not obj:
        return Http404

    access_key = req_user.profile.access_key
    secret_key = req_user.profile.secret_key

    if not secret_key or not secret_key:
        return Http404

    s3 = init_s3_connection(access_key, secret_key)
    tmp = build_tmp_filename()
    with open(tmp, 'wb') as fp:
        s3.download_fileobj(
            Bucket=obj.bucket.name,
            Key=obj.key,
            Fileobj=fp
        )

    res = StreamingHttpResponse(file_iter(tmp))
    res['Content-Type'] = 'application/octet-stream'
    res['Content-Disposition'] = 'attachment;filename="%s"' % obj.name.encode().decode('ISO-8859-1')
    return res


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