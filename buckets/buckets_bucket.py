import time

from django.conf import settings
from django.db.models import Q
from rest_framework.decorators import api_view
from rest_framework.exceptions import ParseError, NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.status import HTTP_201_CREATED
from rest_framework.views import APIView
from rest_framework.permissions import DjangoModelPermissions
from rgwadmin.exceptions import NoSuchKey, NoSuchBucket

from buckets.models import BucketRegion, BucketAcl, Buckets
from buckets.serializer import BucketSerialize
from common.func import clean_post_data, s3_client, rgw_client
from common.verify import verify_pk, verify_in_array, verify_true_false, verify_bucket_name


class BucketEndpoint(APIView):
    model = Buckets
    queryset = model.objects.none()
    permission_classes = (DjangoModelPermissions,)

    fields = [
        ('*name', str, verify_bucket_name),
        ('*bucket_region_id', int, (verify_pk, BucketRegion)),
        ('version_control', bool, verify_true_false),
        ('*permission', str, (verify_in_array, ('private', 'public-read', 'public-read-write'))),
    ]

    pk_field = [
        ('*bucket_id', int, (verify_pk, Buckets))
    ]

    def get(self, request):
        bucket_obj = self.model.objects.\
            select_related('user').\
            select_related('user__profile'). \
            select_related('bucket_region')
        # 管理员查询所有用户的bucket，非管理员仅可查看自己的bucket
        if not request.user.is_superuser:
            # 查询已授到用户的所有桶列表
            authorized_bucket = BucketAcl.objects.filter(user=request.user).values_list('bucket_id')
            authorized_bucket_list = [i[0] for i in authorized_bucket]
            self.queryset = bucket_obj.filter(
                Q(user=request.user) |
                Q(bucket_id__in=authorized_bucket_list)
            )
        else:
            kw = request.GET.get('keyword', None)
            if kw:
                self.queryset = bucket_obj.filter(
                    Q(user__first_name=kw) |
                    Q(user__username=kw) |
                    Q(name__contains=kw) |
                    Q(bucket_region__name=kw)
                )
            else:
                self.queryset = bucket_obj.all()
        # 获取分页参数并进行分页
        try:
            cur_page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('size', settings.PAGE_SIZE))
        except ValueError:
            cur_page = 1
            page_size = settings.PAGE_SIZE

        page = PageNumberPagination()
        page.page_size = page_size
        page.number = cur_page
        page.max_page_size = 20

        ret = page.paginate_queryset(self.queryset.order_by('-bucket_id'), request)
        ser = BucketSerialize(ret, many=True)
        # 返回计求数据
        return Response({
            'code': 0,
            'msg': 'success',
            'data': ser.data,
            'page_info': {
                'record_count': self.queryset.count(),
                'page_size': page_size,
                'current_page': page.number
            }
        })

    def post(self, request):
        data = clean_post_data(request.body, tuple(self.fields))
        if query_bucket_exist(data['name']):
            raise ParseError(detail='the bucket is already exist!')
        # 判断容量是否足够
        q = request.user.capacity_quota
        if not q or not q.valid():
            raise ParseError(detail='user capacity not enough')

        bucket_region = BucketRegion.objects.get(pk=data['bucket_region_id'])
        if bucket_region.state != 'e':
            raise ParseError('region is not enable state')

        # 使用用户key创建bucket
        s3 = s3_client(data['bucket_region_id'], request.user.username)
        s3.create_bucket(
            Bucket=data['name'],
            ACL=data['permission'],
        )

        if data['version_control']:
            s3.put_bucket_versioning(
                Bucket=data['name'],
                VersioningConfiguration={
                    'MFADelete': 'Disabled',
                    'Status': 'Enabled',
                },
            )

        # 本地数据库插入记录
        self.model.objects.create(
            name=data['name'],
            bucket_region_id=data['bucket_region_id'],
            version_control=data['version_control'],
            user=request.user,
            permission=data['permission'],
            start_time=int(time.time()),
        )

        return Response({
            'code': 0,
            'msg': 'success',
        }, status=HTTP_201_CREATED)

    def delete(self, request):
        data = clean_post_data(request.body, tuple(self.pk_field))
        bucket = self.model.objects.select_related('bucket_region').get(pk=data['bucket_id'])
        if bucket.user != request.user and not request.user.is_superuser:
            raise ParseError(detail='illegal delete bucket')
        try:
            # ceph集群删除bucket
            rgw = rgw_client(bucket.bucket_region.reg_id)
            rgw.remove_bucket(bucket=bucket.name, purge_objects=True)
            # 删除数据记录
            bucket.delete()
        except NoSuchKey:
            raise ParseError('delete bucket failed, purge objects not found any key')

        except NoSuchBucket:
            raise ParseError('delete bucket failed, not found this bucket')

        except Exception as e:
            raise ParseError(detail=str(e))

        return Response({
            'code': 0,
            'msg': 'success'
        })


@api_view(('GET',))
def query_bucket_name_exist_endpoint(request):
    """
    查询bucket是否已经存在
    """
    name = request.GET.get('name', None)
    ret = query_bucket_exist(name)
    return Response({
        'code': 0,
        'msg': 'success',
        'exist': ret
    })


@api_view(('GET',))
def get_bucket_detail_endpoint(request):
    """
    利用rgw读取bucket详情
    """
    bucket_name = request.GET.get('bucket_name', None)
    req_user = request.user

    try:
        b = Buckets.objects.select_related('bucket_region').get(name=bucket_name)
    except Buckets.DoesNotExist:
        raise NotFound(detail='not found this bucket')

    if b.user != req_user or not req_user.is_superuser:
        raise ParseError(detail='this bucket is not own you')

    try:
        rgw = rgw_client(b.bucket_region.reg_id)
        data = rgw.get_bucket(bucket=bucket_name)
    except Exception as e:
        raise ParseError(detail=str(e))

    return Response({
        'code': 0,
        'msg': 'success',
        'data': data
    })


def query_bucket_exist(name):
    """
    查询bucket是否存在
    """
    try:
        Buckets.objects.get(name=name)
    except Buckets.DoesNotExist:
        return False
    else:
        return True