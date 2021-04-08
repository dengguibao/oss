import time
from rest_framework.permissions import AllowAny
from rest_framework.status import HTTP_201_CREATED
from rest_framework.exceptions import ParseError, NotAuthenticated, NotFound
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import api_view, permission_classes
from django.conf import settings
from django.http import StreamingHttpResponse
from django.contrib.auth.models import AnonymousUser
from buckets.models import Buckets, BucketAcl
from django.db.models import Q
from common.verify import (
    verify_body, verify_object_name,
    verify_field, verify_object_path,
    verify_bucket_name, verify_pk, verify_in_array
)
from common.func import verify_path, build_tmp_filename, file_iter, s3_client
from .serializer import ObjectsSerialize
from .models import Objects, ObjectAcl
import hashlib
import os


@api_view(('POST',))
@permission_classes((AllowAny,))
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
        raise ParseError(detail=data)
    # 检验bucket name是否为非法
    try:
        b = Buckets.objects.select_related('bucket_region').get(name=data['bucket_name'])
    except Buckets.DoesNotExist:
        raise NotFound(detail='not fount this bucket')

    bucket_acl = b.bucket_acl.get().permission

    if isinstance(req_user, AnonymousUser) and bucket_acl != 'public-read-write':
        raise NotAuthenticated(detail='this bucket access policy is not public read write')

    if bucket_acl != 'public-read-write' and req_user.id != b.user_id:
        raise ParseError(detail='bucket and user not match')

    try:
        if 'path' in data:
            # 验证目录是否在正确的bucket下面
            data['path'] = data['path'].replace(',', '/')
            p = verify_path(data['path'])

            if not p or p.owner != req_user or p.bucket.name != data['bucket_name']:
                raise ParseError(detail='illegal path')

            key = data['path'] + data['folder_name'] + '/'
        else:
            key = data['folder_name'] + '/'

        # 初始化s3客户端
        s3 = s3_client(b.bucket_region.reg_id, b.user.username)
        d = s3.put_object(Bucket=b.name, Body=b'', Key=key)
        # 创建空对象，目录名为空对象
        record_data = {
            'name': data['folder_name'] + '/',
            'bucket': b,
            'etag': d['ETag'] if 'ETag' in d else None,
            'version_id': d['VersionId'] if 'VersionId' in d else None,
            'type': 'd',
            'key': key,
            'root': data['path'] if 'path' in data else None,
            'owner': b.user if bucket_acl == 'public-read-write' else req_user
        }
        Objects.objects.create(**record_data)

        # if b.version_control:
        #     Objects.objects.create(**record_data)
        # else:
        #     Objects.objects.update_or_create(**record_data)
        # Objects.objects.update_or_create(
        #     name=data['folder_name'] + '/',
        #     bucket=b,
        #     etag=d['ETag'] if 'ETag' in d else None,
        #     version_id=d['VersionId'] if 'VersionId' in d else None,
        #     type='d',
        #     key=key,
        #     root=data['path'] if 'path' in data else None,
        #     owner=req_user
        # )

    except Exception as e:
        raise ParseError(detail=str(e))

    return Response({
        'code': 0,
        'msg': 'success'
    })


@api_view(('DELETE',))
@permission_classes((AllowAny,))
def delete_object_endpoint(request):
    req_user = request.user
    # 验证obj_id是否为非法id
    try:
        obj_id = request.GET.get('obj_id', 0)
        o = Objects.objects.select_related('bucket').select_related('bucket__bucket_region').get(obj_id=int(obj_id))
    except Objects.DoesNotExist:
        raise NotFound(detail='not found this object resource')

    object_acl = o.object_acl.get().permission

    if (isinstance(req_user, AnonymousUser) and object_acl != 'public-read-write') or \
            object_acl != 'public-read-write' and o.owner != req_user:
        raise NotAuthenticated(detail='permission denied')

    try:
        s3 = s3_client(o.bucket.bucket_region.reg_id, req_user.username)
        delete_list = []
        # 如果删除的对象为目录，则删除该目录下的所有一切对象
        if o.type == 'd':
            root_pth = '' if o.root is None else o.root
            obj_name = o.name
            key = root_pth + obj_name
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
        raise ParseError(detail=str(e))

    return Response({
        'code': 0,
        'msg': 'success'
    })


@api_view(('GET',))
@permission_classes((AllowAny,))
def list_objects_endpoint(request):

    req_user = request.user
    path = request.GET.get('path', None)
    bucket_name = request.GET.get('bucket_name', None)

    try:
        b = Buckets.objects.get(name=bucket_name)
    except Buckets.DoesNotExist:
        raise NotFound(detail='not found bucket')
    bucket_acl = b.bucket_acl.get().permission
    if isinstance(req_user, AnonymousUser) and 'public' not in bucket_acl:
        raise NotAuthenticated(detail='this bucket access policy is private')

    print(b.user, req_user)
    if b.user != req_user and 'public' not in bucket_acl:
        raise NotAuthenticated(detail='bucket owner not match')

    res = Objects.objects.select_related('bucket').select_related('owner').filter(bucket=b)

    if path:
        res = res.filter(root=path.replace(',', '/'))
    else:
        res = res.filter(Q(root=None) | Q(root=''))

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
@permission_classes((AllowAny,))
def put_object_endpoint(request):
    req_user = request.user
    bucket_name = request.POST.get('bucket_name', None)
    # filename = request.POST.get('filename', None)
    file = request.FILES.get('file', None)
    path = request.POST.get('path', None)
    permission = request.POST.get('permission', None)

    # 如果没有文件，则直接响应异常
    if not file or not bucket_name:
        raise ParseError(detail='some required field is mission')

    filename = file.name
    for i in [',', '/', '\\']:
        if i in filename:
            raise ParseError(detail='filename contains some special char')

    # 验证bucket是否为异常bucket
    try:
        b = Buckets.objects.select_related('bucket_region').get(name=bucket_name)
    except Buckets.DoesNotExist:
        raise NotFound(detail='not found this bucket')

    bucket_acl = b.bucket_acl.get().permission

    if b.user != req_user and 'public-read-write' != bucket_acl:
        raise NotAuthenticated(detail='bucket owner not match')

    if isinstance(req_user, AnonymousUser) and bucket_acl != 'public-read-write':
        raise NotAuthenticated(detail='this bucket access ACL is not contain public-read-write')

    object_acl = ('private', 'public-read', 'public-read-write')

    if not permission or permission not in object_acl:
        permission = BucketAcl.objects.get(bucket=b).permission

    # 验证路程是否为非常路径（目录）
    p = False
    if path:
        path = path.replace(',', '/')
        p = verify_path(path)

    if p and p.owner != req_user and p.bucket.name != bucket_name:
        raise ParseError(detail='illegal path')

    # 验证文件名是否超长
    if len(filename) > 1024:
        raise ParseError(detail='filename is too long')

    # 将用户上传的文件写入临时文件，生成md5，然后再分批写入后端rgw
    temp_file = build_tmp_filename()
    md5 = hashlib.md5()
    with open(temp_file, 'wb') as f:
        for chunk in file.chunks():
            md5.update(chunk)
            f.write(chunk)

    try:
        s3 = s3_client(b.bucket_region.reg_id, b.user.username)
        if p:
            root = path
        else:
            root = ''

        if b.version_control:
            file_key = root + '%s_%s' % (
                str(time.time()).replace('.', ''),
                filename
            )
        else:
            file_key = root+filename

        # 利用s3接口进行数据上传至rgw
        mp = s3.create_multipart_upload(
            Bucket=b.name,
            Key=file_key,
            ACL=permission
        )
        with open(temp_file, 'rb') as fp:
            n = 1
            parts = []
            while True:
                data = fp.read(5 * 1024 ** 2)
                if not data:
                    break
                x = s3.upload_part(
                    Body=data,
                    Bucket=b.name,
                    ContentLength=len(data),
                    Key=file_key,
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
                Key=file_key,
                UploadId=mp['UploadId'],
                MultipartUpload={'Parts': parts}
            )

        # 创建或更新数据库
        record_data = {
            'name': filename,
            'bucket_id': b.bucket_id,
            'type': 'f',
            'root': root,
            'file_size': file.size,
            'key': file_key,
            'md5': md5.hexdigest(),
            'etag': d['ETag'] if 'ETag' in d else None,
            'version_id': d['VersionId'] if 'VersionId' in d else None,
            'owner_id': b.user.id if bucket_acl == 'public-read-write' else req_user.id
        }
        if b.version_control:
            upload_obj = Objects.objects.create(**record_data)
        else:
            upload_obj, create = Objects.objects.update_or_create(**record_data)

        ObjectAcl.objects.update_or_create(
            object=upload_obj,
            permission=permission,
            user_id=b.user.id if bucket_acl == 'public-read-write' else req_user.id,
        )
        # 删除临时文件
        os.remove(temp_file)

    except Exception as e:
        raise ParseError(detail=str(e))

    return Response({
        'code': 0,
        'msg': 'success'
    }, status=HTTP_201_CREATED)


@api_view(('GET',))
@permission_classes((AllowAny,))
def download_object_endpoint(request):
    try:
        obj_id = int(request.GET.get('obj_id', None))
        obj = Objects.objects.select_related("bucket").select_related('bucket__bucket_region').get(obj_id=obj_id)
    except Objects.DoesNotExist:
        raise NotFound(detail='not found this object resource')

    obj_perm = obj.object_acl.get().permission

    # 判断资源是否为公共可读
    if 'public' not in obj_perm and isinstance(request.user, AnonymousUser):
        raise NotAuthenticated(detail='this resource is private')

    if ('public' not in obj_perm and obj.owner != request.user) or obj.type == 'd':
        raise ParseError(detail='this file owner is not of you or download object is directory')

    s3 = s3_client(obj.bucket.bucket_region.reg_id, obj.owner.username)
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


@api_view(('PUT',))
def set_object_acl_endpoint(request):
    fields = (
        ('*obj_id', int, (verify_pk, Objects)),
        ('*permission', str, (verify_in_array, ('private', 'public-read', 'public-read-write')))
    )
    data = verify_field(request.data, fields)
    if not isinstance(data, dict):
        raise ParseError(detail=data)

    o = Objects.objects.select_related('bucket').select_related('bucket__bucket_region').get(obj_id=data['obj_id'])

    if o.owner != request.user and o.bucket.user != request.user:
        raise NotAuthenticated(detail='user and bucket owner and object owner not match')

    try:
        s3 = s3_client(o.bucket.bucket_region.reg_id, request.user.username)
        s3.put_object_acl(
            ACL=data['permission'],
            Bucket=o.bucket.name,
            Key=o.key
        )
        o_acl = o.object_acl.get()
        o_acl.permission = data['permission']
        o_acl.save()
    except Exception as e:
        raise ParseError(detail=str(e))

    return Response({
        'code': 0,
        'msg': 'success'
    })


@api_view(('GET',))
def query_object_acl_endpoint(request):
    obj_id = request.GET.get('obj_id', None)
    try:
        o = Objects.objects.get(obj_id=int(obj_id))
    except Objects.DoesNotExist:
        raise NotFound(detail='not found object')

    b = o.bucket
    bucket_acl = b.bucket_acl.get().permission
    object_acl = o.object_acl.get().permission

    if 'public' not in bucket_acl and isinstance(request.user, AnonymousUser):
        raise NotAuthenticated(detail='bucket access permission not contain public-read or public-read-write')

    if 'public' not in bucket_acl and request.user != o.owner and request.user != b.user:
        raise NotAuthenticated(detail='object and owner not match')

    return Response({
        'code': 0,
        'msg': 'success',
        'permission': object_acl
    })
