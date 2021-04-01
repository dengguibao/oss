from rest_framework.status import (
    HTTP_201_CREATED, HTTP_404_NOT_FOUND,
    HTTP_400_BAD_REQUEST, HTTP_403_FORBIDDEN
)
from rest_framework.exceptions import ParseError
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import api_view
from django.conf import settings
from django.http.response import Http404
from django.http import StreamingHttpResponse
from buckets.models import Buckets
from django.db.models import Q
from common.verify import (
    verify_body, verify_object_name,
    verify_field, verify_object_path, verify_bucket_name
)
from common.func import init_s3_connection, verify_path, build_tmp_filename, file_iter
from .serializer import ObjectsSerialize
from .models import Objects
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
    # 检验字段
    data = verify_field(request.body, _fields)
    if not isinstance(data, dict):
        return Response({
            'code': 1,
            'msg': data
        }, status=HTTP_400_BAD_REQUEST)
    # 检验bucket name是否为非法
    try:
        b = Buckets.objects.get(name=data['bucket_name'])
    except:
        b = None
    if not b or req_user.id != b.user_id:
        return Response({
            'code': 2,
            'msg': 'illegal request, error bucket name'
        })

    # 验证access_key与secret_key
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
            data['path'] = data['path'].replace(',', '/')
            p = verify_path(data['path'])

            if not p or p.owner != req_user or p.bucket.name != data['bucket_name']:
                return Response({
                    'code': 1,
                    'msg': 'path error'
                }, status=HTTP_400_BAD_REQUEST)

            key = data['path']+data['folder_name']+'/'
        else:
            key = data['folder_name']+'/'

        # 初始化s3客户端
        s3 = init_s3_connection(access_key, secret_key)
        d = s3.put_object(Bucket=b.name, Body=b'', Key=key)
        # 创建空对象，目录名为空对象
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
    # 验证obj_id是否为非法id
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

    # get access_key secret_key
    access_key = req_user.profile.access_key
    secret_key = req_user.profile.secret_key
    try:
        s3 = init_s3_connection(access_key, secret_key)
        delete_list = []
        # 如果删除的对象为目录，则删除该目录下的所有一切对象
        if o.type == 'd':
            root_pth = '' if o.root is None else o.root
            obj_name = o.name
            key = root_pth+obj_name
            delete_list.append(
                (o.obj_id, o.key)
            )
            for i in Objects.objects.filter(root__startswith=key, owner=req_user, bucket=o.bucket).all():
                delete_list.append(
                    (i.obj_id, i.key)
                )
        # 如果删除的对象是文件，则只该对象
        if o.type == 'f':
            delete_list.append(
                (o.obj_id, o.key)
            )

        # 使用s3 client删除对象和对应的数据库映射记录
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
    else:
        res = res.filter(Q(root=None) | Q(root=''))

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
    ret = page.paginate_queryset(res.order_by('type', '-obj_id'), request)
    ser = ObjectsSerialize(ret, many=True)
    return Response({
        'code': 0,
        'msg': 'success',
        'data': ser.data,
        'page_info': {
            'record_count': len(res),
            'pag_size': size,
            'current_page': cur_page,
        }
    })


@api_view(('PUT', 'POST',))
def put_object_endpoint(request):
    req_user = request.user
    bucket_name = request.POST.get('bucket_name', None)
    # filename = request.POST.get('filename', None)
    file = request.FILES.get('file', None)
    path = request.POST.get('path', None)
    # 如果没有文件，则直接响应异常
    if not file or not bucket_name:
        return Response({
            'code': 1,
            'msg': 'some required field is mission!'
        }, status=HTTP_400_BAD_REQUEST)

    filename = file.name
    if ',' in filename:
        raise ParseError({
            'detail': 'filename contain special char'
        })

    # 验证bucket是否为异常bucket
    try:
        b = Buckets.objects.get(user=req_user, name=bucket_name)
    except:
        err = True
    else:
        err = False

    if err:
        return Response({
            'code': 1,
            'msg': 'not found this bucket'
        })

    # 验证路程是否为非常路径（目录）
    if path:
        path = path.replace(',', '/')
        p = verify_path(path)

    if p and p.owner != req_user and p.bucket.name != bucket_name:
        return Response({
            'code': 1,
            'msg': 'path error'
        }, status=HTTP_400_BAD_REQUEST)

    # 验证文件名是否超长
    if len(filename) > 63:
        return Response({
            'code': 1,
            'msg': 'filename to long'
        }, status=HTTP_400_BAD_REQUEST)

    # 将用户上传的文件写入临时文件，生成md5，然后再分批写入后端rgw
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
        if p:
            root = path
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
    }, status=HTTP_201_CREATED)


@api_view(('GET',))
def download_object_endpoint(request):
    req_user = request.user
    try:
        obj_id = int(request.GET.get('obj_id', None))
        obj = Objects.objects.select_related("bucket").get(obj_id=obj_id)
    except:
        pass

    if (obj and obj.owner != req_user) or not obj or obj.type == 'd':
        raise Http404

    access_key = req_user.profile.access_key
    secret_key = req_user.profile.secret_key

    if not secret_key or not secret_key:
        raise Http404

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
