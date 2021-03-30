from rest_framework.permissions import AllowAny
from rest_framework.status import (
    HTTP_201_CREATED, HTTP_404_NOT_FOUND,
    HTTP_400_BAD_REQUEST
)
from django.db.models import Q
from rest_framework.exceptions import ParseError
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from django.http.response import Http404
from django.http import StreamingHttpResponse
from user.models import Profile
from buckets.models import Buckets
from common.func import verify_path, build_tmp_filename, init_s3_connection, file_iter
from objects.serializer import ObjectsSerialize
from objects.models import Objects
import hashlib


def verify_request_key_value(func):
    def dec(request, *args, **kwargs):
        access_key = request.GET.get('access_key', None)
        secret_key = request.GET.get('secret_key', None)
        bucket_name = request.GET.get('bucket', None)
        path = request.GET.get('path', None)

        if not bucket_name or not access_key or not secret_key:
            return Response({
                'code': 1,
                'msg': 'not found key or bucket from request args'
            }, status=HTTP_400_BAD_REQUEST)

        try:
            profile = Profile.objects.select_related('user'). \
                get(access_key=access_key, secret_key=secret_key, phone_verify=1)
            bucket = Buckets.objects.get(name=bucket_name, user=profile.user)
        except:
            return Response({
                'code': 1,
                'msg': 'invalid key or bucket'
            }, status=HTTP_400_BAD_REQUEST)

        if path:
            path = path.replace(',', '/')
            p = verify_path(path)
            if not path or not p or p.owner != profile.user or p.bucket != bucket:
                return Response({
                    'code': 1,
                    'msg': 'path is wrong'
                }, status=HTTP_400_BAD_REQUEST)

        if 'multipart' not in request.content_type:
            request.data['bucket_name'] = bucket_name
            request.data['access_key'] = access_key
            request.data['secret_key'] = secret_key
            request.data['profile'] = profile
            request.data['bucket'] = bucket

        return func(request, *args, **kwargs)
    return dec


@api_view(('PUT',))
@permission_classes((AllowAny,))
@verify_request_key_value
def put_object_endpoint(request):

    # filename = request.GET.get('filename', None)
    md5 = request.GET.get('md5', None)
    post_file = request.FILES.get('file', None)

    if not post_file or post_file.size == 0:
        raise ParseError({
            'detail': 'no upload file'
        })

    filename = post_file.name
    file_size = post_file.size

    if ',' in filename:
        raise ParseError({
            'detail': 'filename contain special char'
        })

    path = request.GET.get('path', None)
    bucket_name = request.GET.get('bucket', None)
    access_key = request.GET.get('access_key', None)
    secret_key = request.GET.get('secret_key', None)

    profile = Profile.objects.get(secret_key=secret_key, access_key=access_key)
    bucket = Buckets.objects.get(name=bucket_name, user=profile.user)

    if path:
        path = path.replace(',', '/')

    temp_file = build_tmp_filename()
    content_md5 = hashlib.md5()
    with open(temp_file, 'wb') as f:
        for chunk in post_file.chunks():
            content_md5.update(chunk)
            f.write(chunk)

    file_md5 = content_md5.hexdigest()

    if md5 and file_md5 != md5:
        return Response({
            'code': 2,
            'msg': 'md5 verify failed'
        }, status=HTTP_400_BAD_REQUEST)
    # try:
    s3 = init_s3_connection(access_key, secret_key)
    mp = s3.create_multipart_upload(Bucket=bucket_name, Key=path + filename)
    with open(temp_file, 'rb') as fp:
        n = 1
        parts = []
        while True:
            data = fp.read(5 * 1024 ** 2)
            if not data:
                break
            x = s3.upload_part(
                Body=data,
                Bucket=bucket_name,
                ContentLength=len(data),
                Key=path + filename,
                UploadId=mp['UploadId'],
                PartNumber=n
            )
            parts.append({
                'ETag': x['ETag'].replace('"', ''),
                'PartNumber': n
            })
            n += 1

        ret = s3.complete_multipart_upload(
            Bucket=bucket_name,
            Key=path + filename,
            UploadId=mp['UploadId'],
            MultipartUpload={'Parts': parts}
        )

    Objects.objects.update_or_create(
        name=filename,
        bucket=bucket,
        type='f',
        root=path,
        md5=file_md5,
        key=path + filename,
        file_size=file_size,
        etag=ret['ETag'] if 'ETag' in ret else None,
        owner=bucket.user
    )
    # except Exception as e:
    #     return Response({
    #         'code': 3,
    #         'msg': 'upload failed',
    #         'error': str(e)
    #     })

    return Response({
        'code': 0,
        'msg': 'success',
        'data': ret
    }, status=HTTP_201_CREATED)


@api_view(('DELETE',))
@permission_classes((AllowAny,))
@verify_request_key_value
def delete_object_endpoint(request):
    profile = request.data['profile']
    bucket = request.data['bucket']

    bucket_name = request.data['bucket_name']
    access_key = request.data['access_key']
    secret_key = request.data['secret_key']

    key = request.GET.get('key', None)
    if key:
        key = key.replace(',', '/')
    try:
        s3 = init_s3_connection(access_key, secret_key)
        file_obj = Objects.objects.get(key=key, owner=profile.user, bucket=bucket)
        delete_list = []
        if file_obj.type == 'd':
            root_pth = ('' if file_obj.root is None else file_obj.root) + file_obj.name
            for i in Objects.objects.filter(owner=file_obj.owner, root__startswith=root_pth, bucket=bucket):
                delete_list.append((i.obj_id, i.key))
        else:
            delete_list.append((file_obj.obj_id, file_obj.key))

        for del_id, del_key in delete_list:
            s3.delete_object(
                Bucket=bucket_name,
                Key=del_key
            )
            Objects.objects.get(obj_id=del_id).delete()
    except Exception as e:
        return Response({
            'code': 3,
            'msg': 'delete object failed',
            'error': str(e)
        })

    return Response({
        'code': 0,
        'msg': 'success'
    })


# @api_view(('PUT',))
# @permission_classes((AllowAny,))
# @verify_request_key_value
# def multi_part_upload_endpoint(request, stage):
#     filename = request.GET.get('filename', None)
#     upload_id = request.GET.get('upload_id', 0)
#     part_num = request.GET.get('part_num', 0)
#
#     if stage not in('create', 'upload', 'completed') or not filename:
#         return Response({
#             'code': 1,
#             'msg': 'illegal request'
#         }, status=HTTP_400_BAD_REQUEST)
#
#     if stage == 'upload' and (len(request.body) < 5*1024**2 or upload_id == 0 or part_num == 0):
#         return Response({
#             'code': 1,
#             'msg': 'upload tage has error, upload body is too small or error upload_id or error part_num'
#         })
#
#     if stage == 'completed' and upload_id == 0:
#         return Response({
#             'code': 1,
#             'msg': 'completed stage, upload_id error'
#         })
#
#     bucket = request.data['bucket']
#     path = request.data['path'] if 'path' in request.data else None
#     bucket_name = request.data['bucket_name']
#     access_key = request.data['access_key']
#     secret_key = request.data['secret_key']
#
#     try:
#         s3 = init_s3_connection(access_key, secret_key)
#         if stage == 'create':
#             ret = s3.create_multipart_upload(Bucket=bucket_name, Key=path + filename[:63])
#         if stage == 'upload':
#             ret = s3.upload_part(
#                 Body=request.body,
#                 Bucket=bucket_name,
#                 ContentLength=len(request.body),
#                 Key=path + filename[:63],
#                 UploadId=upload_id,
#                 PartNumber=part_num
#             )
#         if stage == 'completed':
#             ret = s3.complete_multipart_upload(
#                 Bucket=bucket_name,
#                 Key=path + filename,
#                 UploadId=upload_id
#             )
#             Objects.objects.create(
#                 name=filename,
#                 bucket=bucket,
#                 type='f',
#                 root=path,
#                 file_size=-1,
#                 key=path + filename,
#                 md5='',
#                 etag=ret['ETag'] if 'ETag' in ret else None,
#                 owner=bucket.user
#             )
#     except Exception as e:
#         return Response({
#             'code': 3,
#             'msg': 'failed!',
#             'error': str(e)
#         }, status=HTTP_400_BAD_REQUEST)
#
#     return Response({
#         'code': 0,
#         'msg': 'success',
#         'data': ret
#     })


@api_view(('GET',))
@permission_classes((AllowAny,))
@verify_request_key_value
def download_object_endpoint(request):
    profile = request.data['profile']
    bucket = request.data['bucket']
    bucket_name = request.data['bucket_name']
    access_key = request.data['access_key']
    secret_key = request.data['secret_key']

    key = request.GET.get('key', None)

    if key:
        key = key.replace(',', '/')
        filename = key.split(',')[-1]
    else:
        raise Http404

    try:
        s3 = init_s3_connection(access_key, secret_key)
        file_obj = Objects.objects.get(key=key, owner=profile.user, bucket=bucket)

        if file_obj.type == 'd':
            raise Http404

        tmp = build_tmp_filename()
        with open(tmp, 'wb') as fp:
            s3.download_fileobj(
                Bucket=bucket_name,
                Key=key,
                Fileobj=fp
            )
    except:
        raise Http404

    res = StreamingHttpResponse(file_iter(tmp))
    res['Content-Type'] = 'application/octet-stream'
    res['Content-Disposition'] = 'attachment;filename="%s"' % filename.encode().decode('ISO-8859-1')
    return res


@api_view(('GET',))
@permission_classes((AllowAny,))
@verify_request_key_value
def list_all_objects(request):
    path = request.data['path'] if 'path' in request.data else None
    profile = request.data['profile']
    bucket = request.data['bucket']

    try:
        obj = Objects.objects.select_related('bucket').select_related('owner').filter(owner=profile.user, bucket=bucket)
        if path:
            obj = obj.filter(root=path)
        else:
            obj = obj.filter(Q(root=None) | Q(root=''))

    except:
        return Response({
            'code': 1,
            'msg': 'not found resource'
        }, status=HTTP_404_NOT_FOUND)

    ser = ObjectsSerialize(obj.order_by('type', '-obj_id'), many=True)
    return Response({
        'code': 0,
        'msg': 'success',
        'data': ser.data
    })

