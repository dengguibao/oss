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
from django.contrib.auth.models import User
from botocore.exceptions import ClientError
from common.verify import (
    verify_object_name, verify_object_path,
    verify_bucket_name, verify_pk, verify_in_array,
    verify_username
)
from common.func import verify_path, build_tmp_filename, file_iter, s3_client, clean_post_data
from .serializer import ObjectsSerialize
from .models import Objects, ObjectAcl
import hashlib


@api_view(('POST',))
@permission_classes((AllowAny,))
def create_directory_endpoint(request):
    """
    在指定的bucket内创建目录
    该操作仅在ceph后端创建一个空对象
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

    if bucket_perm == 'private':
        if req_user.id != b.user_id:
            raise ParseError(detail='bucket and user not match')

    if bucket_perm == 'authenticated':
        allow_user_list = BucketAcl.objects. \
            filter(bucket_id=b.bucket_id, permission='authenticated-read-write'). \
            values_list('acl_bid')
        # 在授权列表内，或者桶的拥有者均可以写操作
        if req_user.id not in allow_user_list and req_user != b.user:
            raise NotAuthenticated('current user not permission create directory')

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


@api_view(('DELETE',))
@permission_classes((AllowAny,))
def delete_object_endpoint(request):
    """
    删除文件对象
    """
    req_user = request.user
    # 验证obj_id是否为非法id
    try:
        obj_id = request.GET.get('obj_id', 0)
        o = Objects.objects.select_related('bucket').select_related('bucket__bucket_region').get(obj_id=int(obj_id))
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

    if obj_perm == 'private':
        # 桶拥有者、文件对象拥有者
        if req_user != o.owner and req_user != o.bucket.user:
            raise NotAuthenticated(detail='permission denied')

    if obj_perm == 'authenticated':
        allow_user_list = BucketAcl.objects. \
            filter(bucket_id=o.bucket_id, permission='authenticated-read-write'). \
            values_list('acl_bid')
        # 桶拥有者、已授权用户、文件对象拥有者
        if req_user.id not in allow_user_list and req_user != o.owner and req_user != o.bucket.user:
            raise NotAuthenticated('current user not permission pub object')

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

    if bucket_perm == 'private':
        if req_user != b.user:
            raise NotAuthenticated(detail='current user is not of the bucket owner')

    if bucket_perm == 'authenticated':
        allow_write_user_list = BucketAcl.objects. \
            filter(bucket_id=b.bucket_id, permission='authenticated-read-write'). \
            values_list('acl_bid')
        # 已授权用户和桶拥有者可以列出文件
        if req_user.id not in allow_write_user_list and req_user != b.user:
            raise NotAuthenticated('current user not permission pub object')

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


@api_view(('PUT',))
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
        raise NotFound('not found this bucket')

    bucket_perm = b.permission

    if bucket_perm != 'public-read-write':
        if isinstance(req_user, AnonymousUser):
            raise NotAuthenticated('this bucket access ACL is not contain public-read-write')

    if bucket_perm == 'private':
        if req_user != b.user:
            raise NotAuthenticated(detail='current user is not of the bucket owner')

    if bucket_perm == 'authenticated':
        allow_user_list = BucketAcl.objects.\
            filter(bucket_id=b.bucket_id, permission='authenticated-read-write'). \
            values_list('acl_bid')
        allow_user_list = [i[0] for i in allow_user_list]
        # 桶拥有者、已授权用户
        if req_user.id not in allow_user_list and req_user != b.user:
            raise NotAuthenticated('current user not permission pub object')

    object_allow_acl = ('private', 'public-read', 'public-read-write', 'authenticated')

    if permission is None:
        permission = b.permission
    if permission not in object_allow_acl:
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

    try:
        s3 = s3_client(
            b.bucket_region.reg_id,
            b.user.username
        )
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
        else:
            o, _ = Objects.objects.update_or_create(**record_data)
        o.permission = permission
        o.save()

    except Exception as e:
        raise ParseError(detail=str(e))

    return Response({
        'code': 0,
        'msg': 'success'
    }, status=HTTP_201_CREATED)


@api_view(('GET',))
@permission_classes((AllowAny,))
def download_object_endpoint(request):
    """
    下载指定桶内的指定的文件对象，只能是文件，目录不能下载
    """
    try:
        obj_id = int(request.GET.get('obj_id', None))
        obj = Objects.objects.select_related("bucket").select_related('bucket__bucket_region').get(obj_id=obj_id)
    except Objects.DoesNotExist:
        raise NotFound(detail='not found this object resource')

    if obj.type == 'd':
        raise ParseError('download object is a directory')

    obj_perm = obj.permission

    # 判断资源是否为公共可读
    if 'public' not in obj_perm:
        if isinstance(request.user, AnonymousUser):
            raise NotAuthenticated(detail='this resource is not public-read-write')

    if obj_perm == 'private':
        if obj.owner != request.user and request.user != obj.bucket.user:
            raise ParseError(detail='this file object owner is not of you')

    if obj_perm == 'authenticated':
        allow_user_list = ObjectAcl.objects.\
            filter(object_id=obj.obj_id, permission__startswith='authenticated-read'). \
            values_list('acl_oid')
        allow_user_list = [i[0] for i in allow_user_list]
        # 桶拥有者、已授权、文件拥有者
        if request.user.id not in allow_user_list and request.user != obj.bucket.user and request.user != obj.owner:
            raise NotAuthenticated('current user not permission download the object')

    s3 = s3_client(obj.bucket.bucket_region.reg_id, obj.bucket.user.username)
    tmp = build_tmp_filename()
    try:
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
    except ClientError:
        raise NotFound('not found object from ceph')


@api_view(('PUT',))
def set_object_perm_endpoint(request):
    """
    设置文件对象的读写权限
    """
    fields = (
        ('*obj_id', int, (verify_pk, Objects)),
        ('*permission', str, (verify_in_array, ('private', 'public-read', 'public-read-write', 'authenticated')))
    )
    data = clean_post_data(request.data, fields)

    o = Objects.objects.select_related('bucket').select_related('bucket__bucket_region').get(obj_id=data['obj_id'])

    if o.type == 'd':
        raise ParseError('object is a directory')

    if o.permission == 'private':
        if o.owner != request.user and o.bucket.user != request.user:
            raise NotAuthenticated('user and bucket or user and object ACL not match')

    if o.permission == 'authenticated':
        allow_user_list = ObjectAcl.objects.\
            filter(object_id=o.obj_id, permission='authenticated-read-write'). \
            values_list('acl_oid')
        allow_user_list = [i[0] for i in allow_user_list]
        # 已授权列表、桶归属者、文件对象归属者
        if request.user.id not in allow_user_list and request.user != o.bucket.user and request.user != o.owner:
            raise NotAuthenticated('you are not in the allow access list')

    try:
        if 'authenticated' not in data['permission']:
            s3 = s3_client(o.bucket.bucket_region.reg_id, o.bucket.user.username)
            s3.put_object_acl(
                ACL=data['permission'],
                Bucket=o.bucket.name,
                Key=o.key
            )
        o.permission = data['permission']
        o.save()
    except Exception as e:
        raise ParseError(detail=str(e))

    return Response({
        'code': 0,
        'msg': 'success'
    })


@api_view(('GET',))
def query_object_perm_endpoint(request):
    """
    查询文件对象的读写权限
    """
    obj_id = request.GET.get('obj_id', None)
    try:
        o = Objects.objects.get(obj_id=int(obj_id))
    except Objects.DoesNotExist:
        raise NotFound(detail='not found object')

    if o.type == 'd':
        raise ParseError('object is a directory')

    # if 'public' not in o.permission:
    #     if isinstance(request.user, AnonymousUser):
    #         raise NotAuthenticated(detail='bucket access permission not contain public-read or public-read-write')

    if o.permission == 'private':
        if request.user != o.owner and request.user != o.bucket.user:
            raise NotAuthenticated(detail='object and owner not match')

    if o.permission == 'authenticated':
        allow_user_list = ObjectAcl.objects. \
            filter(object_id=o.obj_id, permission__startswith='authenticated-read'). \
            values_list('acl_oid')
        allow_user_list = [i[0] for i in allow_user_list]
        # 桶拥有者、文件对象拥有者、已授权
        if request.user.id not in allow_user_list and request.user != o.bucket.user and request.user != o.owner:
            raise NotAuthenticated('current user do not allow query this object permission')

    return Response({
        'code': 0,
        'msg': 'success',
        'permission': o.permission
    })


@api_view(('POST', 'GET', 'DELETE'))
def set_object_acl_endpoint(request):
    """
    授权某个用户对桶内指定资源的对象的访问权限
    权限仅支持 认证读、认证读写
    """
    req_user = request.user
    if request.method == 'GET':
        bid = request.GET.get('obj_id', None)

        try:
            o = Objects.objects.get(obj_id=int(bid))
            res = ObjectAcl.objects.select_related('user').filter(object=o).values(
                'user__first_name', 'user__username', 'permission', 'acl_oid', 'object__name'
            )
        except Objects.DoesNotExist:
            raise ParseError('not found this file object')
        except ObjectAcl.DoesNotExist:
            raise ParseError('not found object acl')

        if o.permission == 'private':
            if o.owner != req_user and o.bucket.user != req_user:
                raise ParseError('file object is private')

        if o.permission == 'authenticated':
            allow_user = BucketAcl.objects.filter(
                bucket_id=o.bucket_id,
                permission='authenticated-read-write'
            ).values_list('acl_bid')
            allow_user_list = [i[0] for i in allow_user]
            if req_user.id not in allow_user_list and req_user != o.owner and req_user != o.bucket.user:
                raise ParseError('current user is not in allow access list')

        return Response({
            'code': 0,
            'msg': 'success',
            'data': list(res)
        })

    if request.method == 'POST':
        fields = (
            ('*obj_id', int, (verify_pk, Objects)),
            ('*username', str, verify_username),
            ('*permission', str, (verify_in_array, ('authenticated-read', 'authenticated-read-write')))
        )
        data = clean_post_data(request.body, fields)
        try:
            o = Objects.objects.get(obj_id=int(data['obj_id']))
            user = User.objects.get(username=data['username'])
        except Objects.DoesNotExist:
            raise ParseError('not found this bucket')
        except User.DoesNotExist:
            raise ParseError('not found this user')

        if user.profile.root_uid != req_user.username and user.profile.parent_uid != req_user.username:
            raise ParseError('only support authorized to sub user')

        if o.permission == 'private':
            if o.owner != req_user and o.bucket.user != req_user:
                raise ParseError('file object is private')

        if o.permission == 'authenticated':
            allow_user = BucketAcl.objects.filter(
                bucket_id=o.bucket_id,
                permission='authenticated-read-write'
            ).values_list('acl_bid')
            allow_user_list = [i[0] for i in allow_user]
            if req_user.id not in allow_user_list and req_user != o.owner and req_user != o.bucket.user:
                raise ParseError('current user is not in allow access list')

        ObjectAcl.objects.update_or_create(
            object=o,
            user=user,
            permission=data['permission']
        )

        return Response({
            'code': 0,
            'msg': 'success'
        }, status=HTTP_201_CREATED)

    if request.method == 'DELETE':
        acl_oid = request.GET.get('acl_oid', None)

        try:
            o = ObjectAcl.objects.get(acl_oid=int(acl_oid))
        except ObjectAcl.DoesNotExist:
            raise ParseError('not found resource')
        except TypeError:
            raise ParseError('acl_oid is not a number')

        if o.permission == 'private':
            if o.owner != req_user and o.bucket.user != req_user:
                raise ParseError('file object is private')

        if o.permission == 'authenticated':
            allow_user = BucketAcl.objects.filter(
                bucket_id=o.bucket_id,
                permission='authenticated-read-write'
            ).values_list('acl_bid')
            allow_user_list = [i[0] for i in allow_user]
            if req_user.id not in allow_user_list and req_user != o.owner and req_user != o.bucket.user:
                raise ParseError('current user is not in allow access list')

        o.delete()

        return Response({
            'code': 0,
            'msg': 'success'
        })
