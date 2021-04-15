from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.status import HTTP_201_CREATED, HTTP_200_OK
from rest_framework.exceptions import ParseError, NotFound, NotAuthenticated
from django.db.models import Q
from rgwadmin.exceptions import NoSuchUser, NoSuchKey, NoSuchBucket
from .models import BucketType, Buckets, BucketRegion, BucketAcl
from common.verify import (
    verify_max_length, verify_bucket_name, verify_max_value,
    verify_pk, verify_true_false, verify_in_array, verify_username
)
from django.contrib.auth.models import User
from common.func import rgw_client, s3_client, clean_post_data, verify_super_user
from .serializer import BucketSerialize
import time


@api_view(('GET', 'POST', 'PUT', 'DELETE'))
def set_bucket_type_endpoint(request):
    """
    bucket类型的新增、查询、修改、删除
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
        data = clean_post_data(request.body, tuple(fields))

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
def set_bucket_region_endpoint(request):
    """
    存储区域的查询、新增、修改、删除
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

        if request.user.is_superuser:
            o = o.values()
        else:
            o = o.values('reg_id', 'name')

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
        data = clean_post_data(request.body, tuple(fields))
        verify_super_user(request)

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
def set_buckets_endpoint(request):
    """
    bucket的查询、新增、删除
    """
    req_user = request.user
    if request.method == 'GET':
        # 联合查询bucket user profile表
        obj = Buckets.objects.select_related('user').select_related('user__profile'). \
            select_related('bucket_region')
        # 管理员查询所有用户的bucket，非管理员仅可查看自己的bucket
        if not request.user.is_superuser:
            res = obj.filter(
                Q(user=request.user) |
                Q(user__username=req_user.profile.parent_uid) |
                Q(user__username=req_user.profile.root_uid)
            )
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
             (verify_in_array, ('private', 'public-read', 'public-read-write'))),
        ]
    # 删除操作仅需提供bucket_id，具体删除是会验证删除者身份与bucket拥有者的身份
    if request.method == 'DELETE':
        fields = [
            ('*bucket_id', int, (verify_pk, Buckets))
        ]

    # 数据过滤与验证
    data = clean_post_data(request.body, tuple(fields))

    # 开始进行业务逻辑处理
    try:
        # 创建bucket
        if request.method == 'POST':
            if query_bucket_exist(data['name']):
                raise ParseError(detail='the bucket is already exist!')
            # 判断容量是否足够
            q = request.user.quota
            if not q or not q.calculate_valid_date():
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

            model.objects.create(
                name=data['name'],
                bucket_region_id=data['bucket_region_id'],
                version_control=data['version_control'],
                user=req_user,
                permission=data['permission'],
                start_time=int(time.time()),
                state='e'
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
    except NoSuchKey:
        raise ParseError('delete bucket failed, purge objects not found any key')

    except NoSuchBucket:
        raise ParseError('delete bucket failed, not found this bucket')

    except Exception as e:
        raise ParseError(detail=str(e))

    return Response({
        'code': 0,
        'msg': 'success'
    }, status=HTTP_201_CREATED if request.method == 'POST' else HTTP_200_OK)


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


@api_view(('PUT',))
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
        b_acl = b.bucket_acl.get()
        b_acl.permission = data['permission']
        b_acl.save()
    except Exception as e:
        raise ParseError(detail=str(e))

    return Response({
        'code': 0,
        'msg': 'success'
    })


@api_view(('GET',))
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
        raise NotAuthenticated(detail='bucket and user not match')

    return Response({
        'code': 0,
        'msg': 'success',
        'permission': b.permission
    })


@api_view(('POST', 'GET', 'DELETE'))
def set_bucket_acl_endpoint(request):
    """
    授权某个用户对指定桶内所有资源的对象的访问权限
    权限仅支持认证读、认证读写
    """
    req_user = request.user
    if request.method == 'GET':
        bid = request.GET.get('bucket_id', None)

        try:
            b = Buckets.objects.get(bucket_id=int(bid))
            res = BucketAcl.objects.select_related('user').select_related('bucket').filter(bucket=b).values(
                'user__first_name', 'user__username', 'bucket__name', 'permission', 'acl_bid'
            )
        except Buckets.DoesNotExist:
            raise ParseError('not found this bucket')
        except BucketAcl.DoesNotExist:
            raise ParseError('not found resource')
        except TypeError:
            raise ParseError('acl_bid is not a number')

        if b.user != req_user:
            raise NotAuthenticated('user and bucket__user not match')

        return Response({
            'code': 0,
            'msg': 'success',
            'data': list(res)
        })

    if request.method == 'POST':
        fields = (
            ('*bucket_id', int, (verify_pk, Buckets)),
            ('*username', str, verify_username),
            ('*permission', str, (verify_in_array, ('authenticated-read', 'authenticated-read-write')))
        )
        data = clean_post_data(request.body, fields)
        try:
            bucket = Buckets.objects.get(bucket_id=int(data['bucket_id']))
            user = User.objects.get(username=data['username'])
        except Buckets.DoesNotExist:
            raise ParseError('not found this bucket')
        except User.DoesNotExist:
            raise ParseError('not found this user')

        if user.profile.root_uid != req_user.username and user.profile.parent_uid != req_user.username:
            raise ParseError('only support authorized to sub user')

        if req_user != bucket.user:
            raise ParseError('bucket__user and user not match')

        BucketAcl.objects.update_or_create(
            bucket=bucket,
            user=user,
            permission=data['permission']
        )

        return Response({
            'code': 0,
            'msg': 'success'
        }, status=HTTP_201_CREATED)

    if request.method == 'DELETE':
        acl_bid = request.GET.get('acl_bid', None)

        try:
            b = BucketAcl.objects.get(acl_bid=int(acl_bid))
        except BucketAcl.DoesNotExist:
            raise ParseError('not found resource')

        if b.bucket.user != req_user:
            raise NotAuthenticated('user and bucket__user not match')

        b.delete()
        return Response({
            'code': 0,
            'msg': 'success'
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
