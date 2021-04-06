from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.status import HTTP_201_CREATED, HTTP_200_OK
from rest_framework.exceptions import ParseError, NotFound, NotAuthenticated
from django.db.models import Q
from .models import BucketType, Buckets, BucketRegion, BucketAcl
from common.verify import (
    verify_max_length, verify_body, verify_field, verify_length,
    verify_bucket_name, verify_max_value, verify_pk,
    verify_true_false, verify_in_array
)
from common.func import rgw_client, s3_client
from .serializer import BucketSerialize
import time


@api_view(('GET', 'POST', 'PUT', 'DELETE'))
@verify_body
def set_bucket_type_endpoint(request):
    """
    bucket类型，以及定价
    :param request:
    :return:
    """
    model = BucketType
    fields = [
        ('*name', str, (verify_max_length, 10)),
        ('*price', float, (verify_max_value, 999))
    ]
    id_field = (('*bucket_type_id', int, (verify_max_length, 9)),)

    if request.method == 'GET':
        result = model.objects.all().values()
        return Response({
            'code': 1,
            'msg': 'success',
            'data': result
        })

    if request.method == 'PUT':
        fields.append(id_field[0])

    if request.method == 'DELETE':
        fields = id_field

    # post put delete需要管理员且验证通过才能操作
    if request.method in ('POST', 'PUT', 'DELETE'):
        data = verify_field(request.body, tuple(fields))
        if not isinstance(data, dict):
            raise ParseError(detail=data)

        if not request.user.is_superuser:
            return NotAuthenticated(detail='permission denied!')

    try:
        if request.method == 'POST':
            model.objects.create(**data)

        if request.method == 'PUT':
            bt = model.objects.get(bucket_type_id=data['bucket_type_id'])
            bt.name = data['name']
            bt.price = data['price']
            bt.save()

        if request.method == 'DELETE':
            model.objects.get(bucket_type_id=data['bucket_type_id']).delete()

    except Exception as e:
        raise ParseError(detail=str(e))
    else:
        return Response({
            'code': 0,
            'msg': 'success'
        }, status=HTTP_201_CREATED if request.method == 'POST' else HTTP_200_OK)


@api_view(('GET', 'POST', 'PUT', 'DELETE'))
@verify_body
def set_bucket_region_endpoint(request):
    """
    存储区域
    :param request:
    :return:
    """
    model = BucketRegion
    fields = [
        ('*name', str, (verify_max_length, 20)),
        ('*secret_key', str, (verify_max_length, 50)),
        ('*access_key', str, (verify_max_length, 32)),
        ('*server', str, (verify_max_length, 20)),
    ]
    id_field = (
        ('*reg_id', int, (verify_pk, model)),
    )

    # get请求
    if request.method == 'GET':
        o = model.objects.all()
        # 管理员则可以查看所有的折扣码情况
        if request.user.is_superuser:
            o = o.values()
        else:
            o = o.values(('reg_id', 'name'))

        return Response({
            'code': 0,
            'msg': 'success',
            'data': o
        })

    # put请求，用来更新对象
    if request.method == 'PUT':
        fields.append(id_field[0])

    # delete请求，用来删除对象，只需要提供id即可
    if request.method == 'DELETE':
        fields = id_field

    # post, put, delete方法需要管理员、且验证字段通过才能进行
    if request.method in ('POST', 'PUT', 'DELETE'):
        data = verify_field(request.body, tuple(fields))
        if not isinstance(data, dict):
            raise ParseError(detail=data)

        if not request.user.is_superuser:
            raise NotAuthenticated(detail='permission denied!')

    try:
        if request.method == 'POST':
            if 'https://' in data['server']:
                data['server'] = data['server'][8:]
            if 'http://' in data['server']:
                data['server'] = data['server'][7:]
            model.objects.create(**data)

        # post请求，用来创建对象
        if request.method == 'PUT':
            off = model.objects.get(reg_id=data['reg_id'])
            # print(off, data)
            off.name = data['name']
            off.access_key = data['access_key']
            off.secret_key = data['secret_key']
            off.server = data['server']
            off.save()

        if request.method == 'DELETE':
            model.objects.get(reg_id=data['reg_id']).delete()

    except Exception as e:
        raise ParseError(detail=str(e))

    return Response({
        'code': 0,
        'msg': 'success'
    }, status=HTTP_201_CREATED if request.method == 'POST' else HTTP_200_OK)


@api_view(('GET', 'POST', 'DELETE'))
@verify_body
def set_buckets_endpoint(request):
    req_user = request.user
    if request.method == 'GET':
        # 联合查询bucket user profile表
        obj = Buckets.objects.select_related('user').select_related('user__profile'). \
            select_related('bucket_region')
        # 管理员查询所有用户的bucket，非管理员仅可查看自己的bucket
        if not request.user.is_superuser:
            res = obj.filter(user=request.user)
        else:
            kw = request.GET.get('keyword', None)
            if kw:
                res = obj.filter(
                    Q(user__first_name=kw) |
                    Q(user__username=kw) |
                    Q(name__contains=kw) |
                    Q(bucket_region__name=kw)
                )
            else:
                res = obj.all()
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

        ret = page.paginate_queryset(res.order_by('-bucket_id'), request)
        ser = BucketSerialize(ret, many=True)
        # 返回计求数据
        return Response({
            'code': 0,
            'msg': 'success',
            'data': ser.data,
            'page_info': {
                'record_count': len(res),
                'page_size': page_size,
                'current_page': page.number
            }
        })

    # 没有进行手机验证的不允许继续操作
    if not req_user.profile.phone_verify or \
            not req_user.profile.access_key or \
            not req_user.profile.secret_key:
        raise ParseError(detail='current user has not pass phone verification')

    model = Buckets
    # 新增bucket需要提供的字段以及验证方法
    if request.method == 'POST':
        fields = [
            ('*name', str, verify_bucket_name),
            # 最多购买1TB
            # ('*capacity', int, (verify_max_value, 1024)),
            # ('*bucket_type_id', int, (verify_pk, BucketType)),
            # 仅支持最多购买5年
            # ('*duration', int, (verify_max_value, 365 * 5)),
            # 折扣券
            # ('offset_code', str, (verify_length, 8))
            # ('*bucket_type_id', int, (verify_pk, BucketType)),
            ('*bucket_region_id', int, (verify_pk, BucketRegion)),
            ('version_control', bool, verify_true_false),
            ('*permission', str,
             (verify_in_array, ('private', 'public-read', 'public-read-write', 'authenticated-read'))),
        ]
    # 删除操作仅需提供bucket_id，具体删除是会验证删除者身份与bucket拥有者的身份
    if request.method == 'DELETE':
        fields = [
            ('*bucket_id', int, (verify_pk, Buckets))
        ]

    # 数据过滤与验证
    data = verify_field(request.body, tuple(fields))
    if not isinstance(data, dict):
        raise ParseError(detail=data)

    # 开始进行业务逻辑处理
    try:
        # 创建bucket
        if request.method == 'POST':
            if query_bucket_exist(data['name']):
                raise ParseError(detail='the bucket is already exist!')
            # 判断容量是否足够
            t = request.user.capacity
            if not t or not t.calculate_valid_date():
                raise ParseError(detail='user capacity not enough')

            data['user_id'] = req_user.id
            data['start_time'] = int(time.time())
            data['state'] = 'e'

            # 使用用户key创建bucket
            s3 = s3_client(data['bucket_region_id'], req_user.username)
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

            bucket_obj = model.objects.create(
                name=data['name'],
                bucket_region_id=data['bucket_region_id'],
                version_control=data['version_control'],
                user=req_user,
                start_time=int(time.time()),
                state='e'
            )

            BucketAcl.objects.create(
                permission=data['permission'],
                user=req_user,
                bucket_id=bucket_obj.pk
            )

        if request.method == 'DELETE':
            # 即不是超级管理员，也不是bucket拥有者，提示非异操作
            bucket = model.objects.select_related('bucket_region').get(pk=data['bucket_id'])
            if bucket.user != req_user and not req_user.is_superuser:
                raise ParseError(detail='illegal delete bucket')

            # ceph集群删除bucket
            rgw = rgw_client(bucket.bucket_region.reg_id)
            rgw.remove_bucket(bucket=bucket.name, purge_objects=True)
            # 删除数据记录
            bucket.delete()

    except Exception as e:
        return ParseError(detail=str(e))

    return Response({
        'code': 0,
        'msg': 'success'
    }, status=HTTP_201_CREATED if request.method == 'POST' else HTTP_200_OK)


@api_view(('GET',))
def query_bucket_name_exist_endpoint(request):
    name = request.GET.get('name', None)
    ret = query_bucket_exist(name)
    return Response({
        'code': 0,
        'msg': 'success',
        'exist': ret
    })


@api_view(('GET',))
def get_bucket_detail_endpoint(request):
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
    try:
        Buckets.objects.get(name=name)
    except Buckets.DoesNotExist:
        return False
    else:
        return True

# def get_offset_value(code):
#     try:
#         v = Offset.objects.get(code=code)
#     except:
#         return False
#     else:
#         return v.get_offset_value()
#
#
# def update_off_code(code):
#     v = Offset.objects.get(code=code)
#     v.use_offset_code()
