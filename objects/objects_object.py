import hashlib
import time

from botocore.exceptions import ClientError
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.db.models import Q
from django.http import StreamingHttpResponse
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ParseError, NotFound, NotAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.status import HTTP_201_CREATED

from buckets.models import Buckets, BucketAcl
from common.func import verify_path, s3_client, clean_post_data
from common.tokenauth import verify_permission
from common.verify import verify_bucket_name, verify_object_name, verify_object_path
from objects.models import Objects, ObjectAcl
from objects.serializer import ObjectsSerialize


def verify_bucket_owner_and_permission(o: Buckets, request, perm: str):
    """
    验证文件对象是否有权限访问
    :param o: Buckets model instance
    :param request: WSGI request
    :param perm: authenticated-read, authenticated-read-write
    :return if has permission then pass else raise a exception
    """

    if o.permission == 'private':
        if request.user != o.user:
            return False, 'bucket owner and request user not match'

    if o.permission == 'authenticated':
        allow_user_list = BucketAcl.objects. \
            filter(bucket_id=o.bucket_id, permission__startswith=perm). \
            values_list('user_id')
        allow_user_list = [i[0] for i in allow_user_list]
        # 桶拥有者、已授权
        if request.user.id not in allow_user_list and \
                request.user != o.user:
            return False, 'current user dont authorize access this bucket'

    return True, None


@api_view(('PUT', 'POST'))
@verify_permission(model_name='objects')
@permission_classes((AllowAny,))
def put_object_endpoint(request):
    """
    上传文件对象至bucket
    """
    req_user = request.user
    bucket_name = request.POST.get('bucket_name', None)
    # filename = request.POST.get('filename', None)
    file = request.FILES.get('file', None)
    path = request.POST.get('path', None)
    permission = request.POST.get('permission', None)

    # 如果没有文件，则直接返回400
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
        raise NotFound('not found this bucket')

    bucket_perm = b.permission

    if bucket_perm != 'public-read-write':
        if isinstance(req_user, AnonymousUser):
            raise NotAuthenticated('bucket permission is not public-read-write')

    _, msg = verify_bucket_owner_and_permission(b, request, 'authenticated-read-write')
    if msg:
        raise NotAuthenticated(msg)

    object_allow_acl = ('private', 'public-read', 'public-read-write', 'authenticated')

    if len(permission) == 0:
        permission = b.permission
    if permission and permission not in object_allow_acl:
        raise ParseError('permission value has wrong!')

    # 验证路程是否为非常路径（目录）
    p = False
    if path:
        path = path.replace(',', '/')
        p = verify_path(path)

    if p and p.bucket.name != bucket_name:
        raise ParseError(detail='illegal path')

    # 验证文件名是否超长
    if len(filename) > 1024:
        raise ParseError(detail='filename is too long')

    md5 = hashlib.md5()

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
        file_key = root + filename

    try:
        s3 = s3_client(
            b.bucket_region.reg_id,
            b.user.username
        )

        # 利用s3接口进行数据上传至rgw
        if 'authenticated' not in permission:
            mp = s3.create_multipart_upload(
                Bucket=b.name,
                Key=file_key,
                ACL=permission
            )
        else:
            mp = s3.create_multipart_upload(
                Bucket=b.name,
                Key=file_key,
                # ACL=permission
            )
        n = 1
        parts = []
        for data in file.chunks(chunk_size=5*1024**2):
            md5.update(data)
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
            'owner_id': b.user.id if bucket_perm == 'public-read-write' else req_user.id,
        }
        if b.version_control:
            o = Objects.objects.create(**record_data)
            new = True
        else:
            o, new = Objects.objects.update_or_create(**record_data)
        o.permission = permission
        o.save()

    except Exception as e:
        raise ParseError(detail=str(e))

    ser = ObjectsSerialize(o)
    return Response({
        'code': 0,
        'msg': 'success',
        'data': ser.data,
        'new': new,
    }, status=HTTP_201_CREATED)


@api_view(('POST',))
@permission_classes((AllowAny,))
def create_directory_endpoint(request):
    """
    在指定的bucket内创建目录
    """
    req_user = request.user
    _fields = (
        ('*bucket_name', str, verify_bucket_name),
        ('*folder_name', str, verify_object_name),
        ('path', str, verify_object_path)
    )
    # 检验字段
    data = clean_post_data(request.body, _fields)
    # 检验bucket name是否为非法
    try:
        b = Buckets.objects.select_related('bucket_region').get(name=data['bucket_name'])
    except Buckets.DoesNotExist:
        raise NotFound(detail='not fount this bucket')

    bucket_perm = b.permission

    if bucket_perm != 'public-read-write':
        if isinstance(req_user, AnonymousUser):
            raise NotAuthenticated(detail='anonymous user can not access this bucket')

    _, msg = verify_bucket_owner_and_permission(b, request, 'authenticated-read-write')
    if msg:
        raise NotAuthenticated(msg)

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
        # s3 = s3_client(b.bucket_region.reg_id, b.user.username)
        # d = s3.put_object(Bucket=b.name, Body=b'', Key=key)
        # 创建空对象，目录名为空对象
        record_data = {
            'name': data['folder_name'] + '/',
            'bucket': b,
            'type': 'd',
            'key': key,
            'root': data['path'] if 'path' in data else None,
            # 后端s3使用桶角色对应的ceph uid写入ceph rgw，本地数据库上传者本身
            'owner': b.user if bucket_perm == 'public-read-write' else req_user
        }
        Objects.objects.create(**record_data)

    except Exception as e:
        raise ParseError(detail=str(e))

    return Response({
        'code': 0,
        'msg': 'success'
    })


@api_view(('GET',))
@permission_classes((AllowAny,))
def list_objects_endpoint(request):
    """
    列出桶内的所有文件对象和目录
    """
    req_user = request.user
    path = request.GET.get('path', None)
    bucket_name = request.GET.get('bucket_name', None)

    try:
        b = Buckets.objects.get(name=bucket_name)
    except Buckets.DoesNotExist:
        raise NotFound(detail='not found bucket')

    bucket_perm = b.permission

    if bucket_perm not in ('public-read', 'public-read-write'):
        if isinstance(req_user, AnonymousUser):
            raise NotAuthenticated('this bucket acl is not contain public')

    _, msg = verify_bucket_owner_and_permission(b, request, 'authenticated-read')
    if msg:
        raise NotAuthenticated(msg)

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


@api_view(('DELETE',))
@permission_classes((AllowAny,))
def delete_object_endpoint(request):
    """
    删除文件对象
    """
    req_user = request.user
    # 验证obj_id是否为非法id
    try:
        bucket_name = request.GET.get('bucket_name', '')
        key = request.GET.get('key', '').replace(',', '/')
        o = Objects.objects.select_related('bucket').select_related('bucket__bucket_region').get(
            bucket__name=bucket_name, key=key
        )
    except Objects.DoesNotExist:
        raise NotFound(detail='not found this object resource')

    # 删除文件仅需要具有当前文件对象的权限
    if o.type == 'f':
        obj_perm = o.permission
    # 删除目录需要具有桶权限
    elif o.type == 'd':
        obj_perm = o.bucket.permission
    else:
        obj_perm = 'unknown'

    if obj_perm != 'public-read-write':
        if isinstance(req_user, AnonymousUser):
            raise NotAuthenticated('anonymous user dont allow delete this file or directory')

    _, msg = verify_bucket_owner_and_permission(o.bucket, request, 'authenticated-read-write')
    if msg:
        raise NotAuthenticated(msg)

    try:
        s3 = s3_client(o.bucket.bucket_region.reg_id, o.bucket.user.username)
        delete_list = []
        # 如果删除的对象为目录，则删除该目录下的所有一切对象
        if o.type == 'd':
            root_pth = '' if o.root is None else o.root
            obj_name = o.name
            key = root_pth + obj_name
            delete_list.append(
                (o.obj_id, o.key)
            )
            # 删除目录则需要删除以提指定路程径开头的所有对象
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
def download_object_endpoint(request):
    """
    下载指定桶内的指定的文件对象，只能是文件，目录不能下载
    """
    try:
        bucket_name = request.GET.get('bucket_name', '')
        key = request.GET.get('key', '').replace(',', '/')
        obj = Objects.objects.select_related("bucket").select_related('bucket__bucket_region').get(
            bucket__name=bucket_name, key=key
        )
    except Objects.DoesNotExist:
        raise NotFound(detail='not found this object resource')

    if obj.type == 'd':
        raise ParseError('download object is a directory')

    obj_perm = obj.permission

    # 判断资源是否为公共可读
    if 'public' not in obj_perm:
        if isinstance(request.user, AnonymousUser):
            raise NotAuthenticated(detail='this resource is not public-read-write')

    _, msg = verify_bucket_owner_and_permission(obj.bucket, request, 'authenticated-read')
    if msg:
        raise NotAuthenticated(msg)

    try:
        s3 = s3_client(obj.bucket.bucket_region.reg_id, obj.bucket.user.username)

        file_size = obj.file_size

        def file_content(size):
            n = 0
            transfer_count = 0
            ts = time.time()
            min_unit = 1024**2
            # 下载带宽MB
            if isinstance(request.user, AnonymousUser):
                bandwidth = settings.USER_MIN_BANDWIDTH
            else:
                bandwidth = request.user.bandwidth_quota.user_bandwidth()

            while 1:
                # 分段从上游ceph上面下载字节流数据(单位为字节，非比特，不用转换)
                ret_data = s3.get_object(
                    Bucket=obj.bucket.name,
                    Key=obj.key,
                    Range='bytes=%s-%s' % (n, n+min_unit-1),
                )
                n += min_unit
                data = ret_data['Body'].read()
                transfer_count += min_unit
                # print('already_transfer:', transfer_count, 'bandwidth_transfer:', bandwidth*min_unit, time.time()-ts)
                if transfer_count >= bandwidth*min_unit:
                    if time.time()-ts < 1:
                        time.sleep(1-(time.time()-ts))
                        ts = time.time()
                    transfer_count = 0
                yield data
                if n > file_size:
                    break

        res = StreamingHttpResponse(file_content(file_size))
        res['Content-Type'] = 'application/octet-stream'
        res['Content-Disposition'] = 'attachment;filename="%s"' % obj.name.encode().decode('ISO-8859-1')
        return res

    except ClientError:
        raise NotFound('client error')
    except ConnectionError:
        raise ParseError('connection to upstream server timeout')