from rest_framework.status import (
    HTTP_200_OK, HTTP_201_CREATED, HTTP_404_NOT_FOUND,
    HTTP_400_BAD_REQUEST, HTTP_403_FORBIDDEN
)
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import api_view

from buckets.models import Buckets

from common.verify import (
    verify_body, verify_pk, verify_object_name,
    verify_field, verify_object_path
)
from common.func import init_s3_connection

from .models import Objects


@api_view(('POST',))
@verify_body
def create_directory_endpoint(request):
    req_user = request.user
    _fields = (
        ('*bucket_id', int, (verify_pk, Buckets)),
        ('*folder_name', str, verify_object_name),
        ('path', str, verify_object_path)
    )
    data = verify_field(request.body, _fields)
    if not isinstance(data, dict):
        return Response({
            'code': 1,
            'msg': data
        }, status=HTTP_400_BAD_REQUEST)

    b = Buckets.objects.get(pk=data['bucket_id'])
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
            try:
                Objects.objects.get(name=data['path'], type='d', owner=req_user, bucket_id=data['bucket_id'])
            except:
                return Response({
                    'code': 2,
                    'msg': 'error path'
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
