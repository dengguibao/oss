from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.exceptions import ParseError, NotFound, NotAuthenticated

from common.tokenauth import verify_permission
from .models import Buckets
from common.verify import verify_pk, verify_in_array
from common.func import s3_client, clean_post_data


@api_view(('PUT',))
@verify_permission(model_name='buckets')
def set_bucket_perm_endpoint(request):
    """
    查询bucket的读写权限
    """
    fields = (
        ('*bucket_id', int, (verify_pk, Buckets)),
        ('*permission', str, (verify_in_array, ('private', 'public-read', 'public-read-write', 'authenticated')))
    )
    data = clean_post_data(request.data, fields)

    b = Buckets.objects.select_related('bucket_region').get(bucket_id=data['bucket_id'])

    if request.user != b.user:
        raise NotAuthenticated(detail='bucket and user not match')

    try:
        # authenticated该权限s3上没有，所以不在上游进行处理
        if 'authenticated' != data['permission']:
            s3 = s3_client(b.bucket_region.reg_id, b.user.username)
            s3.put_bucket_acl(
                ACL=data['permission'],
                Bucket=b.name
            )
        # 更新本地数据库
        b.permission = data['permission']
        b.save()
    except Exception as e:
        raise ParseError(detail=str(e))

    return Response({
        'code': 0,
        'msg': 'success'
    })


@api_view(('GET',))
@verify_permission(model_name='buckets')
def query_bucket_perm_endpoint(request):
    """
    查询指定的bucket的读写权限
    """
    bucket_id = request.GET.get('bucket_id', None)
    try:
        b = Buckets.objects.get(bucket_id=bucket_id)
    except Buckets.DoesNotExist:
        raise NotFound(detail='not found bucket')

    if request.user != b.user:
        raise NotAuthenticated(detail='bucket owner and user not match')

    return Response({
        'code': 0,
        'msg': 'success',
        'permission': b.permission
    })