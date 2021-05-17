from rest_framework.exceptions import ParseError, NotFound
from rest_framework.response import Response
from rest_framework.decorators import api_view

from common.tokenauth import verify_permission
from common.verify import verify_pk, verify_in_array
from common.func import s3_client, validate_post_data
from .models import Objects, ObjectAcl

from buckets.models import BucketAcl
from objects.objects_object import PermAction


def verify_file_owner_and_permission(request, perm: PermAction, o: Objects):
    """
    验证文件对象是否有权限访问
    :param o: Objects model instance
    :param request: WSGI request
    :param perm: authenticated-read, authenticated-read-write
    :return if has permission then pass else raise a exception
    """
    if o.permission == 'private':
        if request.user != o.owner and request.user != o.bucket.user:
            raise ParseError('object and owner not match')

    if o.permission == 'authenticated':
        object_authorize_user_list = ObjectAcl.objects.filter(
            object_id=o.obj_id, permission__startswith='authenticated-%s' % perm.value
        ).values_list('user_id', flat=True)

        bucket_authorize_user_list = BucketAcl.objects.filter(
            bucket=o.bucket, permission__startswith='authenticated-%s' % perm.value
        ).values_list('user_id', flat=True)

        allow_user_list = set(list(object_authorize_user_list)+list(bucket_authorize_user_list))
        # 桶拥有者、文件对象拥有者、已授权
        if request.user.id not in allow_user_list and \
                request.user != o.bucket.user and \
                request.user != o.owner:
            raise ParseError('current user cant allow access this object')


@api_view(('PUT',))
@verify_permission(model_name='objects')
def set_object_perm_endpoint(request):
    """
    设置文件对象的读写权限
    :param request: WSGI request
    """
    fields = (
        ('*obj_id', int, (verify_pk, Objects)),
        ('*permission', str, (verify_in_array, ('private', 'public-read', 'public-read-write', 'authenticated')))
    )
    data = validate_post_data(request.data, fields)

    o = Objects.objects.select_related('bucket').select_related('bucket__bucket_region').get(obj_id=data['obj_id'])

    if o.type == 'd':
        raise ParseError('object is a directory')

    verify_file_owner_and_permission(request, PermAction.RW, o)

    try:
        # 当权限为authenticated时，不推送到后端上游服务器
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
@verify_permission(model_name='objects')
def query_object_perm_endpoint(request):
    """
    查询文件对象的读写权限
    :param request: WSGI request
    """
    obj_id = request.GET.get('obj_id', None)
    try:
        o = Objects.objects.get(obj_id=int(obj_id))
    except Objects.DoesNotExist:
        raise NotFound(detail='not found object')

    if o.type == 'd':
        raise ParseError('object is a directory')

    verify_file_owner_and_permission(request, PermAction.R, o)

    return Response({
        'code': 0,
        'msg': 'success',
        'permission': o.permission
    })
