# from django.shortcuts import render
# from django.contrib.auth.models import User
from django.conf import settings

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.status import (
    HTTP_200_OK, HTTP_400_BAD_REQUEST,
    HTTP_201_CREATED, HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND
)
from user.models import Money
from .models import BucketType, Buckets, Offset
from common.verify import (
    verify_max_length, verify_body, verify_field, verify_length,
    verify_bucket_name, verify_max_value, verify_pk
)
from common.func import init_s3_connection, init_rgw_api
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
        }, status=HTTP_200_OK)

    if request.method == 'PUT':
        fields.append(id_field[0])

    if request.method == 'DELETE':
        fields = id_field

    # post put delete需要管理员且验证通过才能操作
    if request.method in ('POST', 'PUT', 'DELETE'):
        data = verify_field(request.body, tuple(fields))
        if not isinstance(data, dict):
            return Response({
                'code': 1,
                'msg': data
            }, status=HTTP_400_BAD_REQUEST)

        if not request.user.is_superuser:
            return Response({
                'code': 2,
                'msg': 'permission deinied!'
            }, status=HTTP_403_FORBIDDEN)

    try:
        if request.method == 'POST':
            model.objects.create(**data)
            status_code = HTTP_201_CREATED

        if request.method == 'PUT':
            bt = model.objects.get(bucket_type_id=data['bucket_type_id'])
            bt.name = data['name']
            bt.price = data['price']
            bt.save()
            status_code = HTTP_200_OK

        if request.method == 'DELETE':
            model.objects.get(bucket_type_id=data['bucket_type_id']).delete()
            status_code = HTTP_200_OK

    except Exception as e:
        return Response({
            'code': 3,
            'msg': 'error, %s' % e.args
        }, status=HTTP_400_BAD_REQUEST)
    else:
        return Response({
            'code': 0,
            'msg': 'success'
        }, status=status_code)


@api_view(('GET', 'POST', 'PUT', 'DELETE'))
@verify_body
def set_offset_endpoint(request):
    """
    折扣码访问入口
    :param request:
    :return:
    """
    model = Offset
    fields = [
        ('*code', str, (verify_length, 8)),
        ('*offset', float, (verify_max_value, 10)),
        ('*max_use_times', int, (verify_max_value, 9999)),
        ('*valid_days', int, (verify_max_value, 365)),
    ]
    id_field = (
        ('*off_id', int, (verify_pk, Offset)),
    )

    # get请求
    if request.method == 'GET':
        # 根据拆扣码查询对应的拆扣
        code = request.GET.get('code', None)
        if code:
            try:
                o = model.objects.get(code=code)
            except:
                return Response({
                    'code': 1,
                    'msg': 'invalid off code',
                }, status=HTTP_404_NOT_FOUND)
            else:
                return Response({
                    'code': 0,
                    'msg': 'success',
                    'data': {
                        'value': o.get_offset_value()
                    }
                }, status=HTTP_200_OK)

        # 管理员则可以查看所有的折扣码情况
        if request.user.is_superuser:
            o = model.objects.all().values()
            return Response({
                'code': 0,
                'msg': 'success',
                'data': o
            }, status=HTTP_200_OK)

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
            return Response({
                'code': 1,
                'msg': data
            }, status=HTTP_400_BAD_REQUEST)

        if not request.user.is_superuser:
            return Response({
                'code': 2,
                'msg': 'permission deinied!'
            }, status=HTTP_403_FORBIDDEN)

    try:
        if request.method == 'POST':
            model.objects.create(**data)
            status_code = HTTP_201_CREATED

        # post请求，用来创建对象
        if request.method == 'PUT':
            off = model.objects.get(off_id=data['off_id'])
            # print(off, data)
            off.code = data['code']
            off.offset = data['offset']
            off.max_use_times = data['max_use_times']
            off.valid_days = data['valid_days']
            off.save()
            status_code = HTTP_200_OK

        if request.method == 'DELETE':
            model.objects.get(off_id=data['off_id']).delete()
            status_code = HTTP_200_OK

    except Exception as e:
        return Response({
            'code': 3,
            'msg': 'error, %s' % e.args
        }, status=HTTP_400_BAD_REQUEST)
    else:
        return Response({
            'code': 0,
            'msg': 'success'
        }, status=status_code)


@api_view(('GET', 'POST', 'DELETE'))
@verify_body
def set_buckets_endpoint(request):
    if request.method == 'GET':
        # 联合查询bucket user profile表
        obj = Buckets.objects.select_related('user').select_related('user__profile')
        # 管理员查询所有用户的bucket，非管理员仅可查看自己的bucket
        if not request.user.is_superuser:
            res = obj.filter(user=request.user)
        else:
            res = obj.all()
        # 获取分页参数并进行分页
        try:
            cur_page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('size', settings.PAGE_SIZE))
        except:
            cur_page = 1
            page_size = settings.PAGE_SIZE

        page = PageNumberPagination()
        page.page_size = page_size
        page.number = cur_page
        page.max_page_size = 20

        ret = page.paginate_queryset(res, request)
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

    req_user = request.user

    # 没有进行手机验证的不允许继续操作
    if not req_user.profile.phone_verify or \
            not req_user.profile.access_key or \
            not req_user.profile.secret_key:
        return Response({
            'code': 1,
            'msg': 'current user has not pass phone verification '
        }, status=HTTP_400_BAD_REQUEST)

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
        ]
    # 删除操作仅需提供bucket_id，具体删除是会验证删除者身份与bucket拥有者的身份
    if request.method == 'DELETE':
        fields = [
            ('*bucket_id', int, (verify_pk, Buckets))
        ]
    # 续期bucket需要提供购买时长 优惠码（可选） bucket_id
    # if request.method == 'PUT':
    #     fields = [
    #         ('*bucket_id', int, (verify_pk, Buckets)),
    #         # 仅支持最多购买5年
    #         ('*duration', int, (verify_max_value, 365 * 5)),
    #         # 折扣券
    #         ('offset_code', str, (verify_length, 8))
    #     ]

    # 数据过滤与验证
    data = verify_field(request.body, tuple(fields))

    if not isinstance(data, dict):
        return Response({
            'code': 1,
            'msg': data
        }, status=HTTP_400_BAD_REQUEST)

    # 开始进行业务逻辑处理
    try:
        # 创建bucket
        if request.method == 'POST':
            if query_bucket_exist(data['name']):
                return Response({
                    'code': 2,
                    'msg': 'the bucket is already exist!'
                }, status=HTTP_400_BAD_REQUEST)

            # bt = BucketType.objects.get(pk=data['bucket_type_id'])
            # price = bt.price
            #
            # m = Money.objects.get(user=req_user)
            #
            # # 默认折扣值为1，即不打拆，也不加价
            # off_value = 1
            # off_code = None
            # if 'offset_code' in data:
            #     off_code = data['offset_code']
            #     off_value = get_offset_value(off_code)
            #     del data['offset_code']

            # 购买容量*每月价*购买月数*折扣优惠
            # need_money = (data['capacity'] * price * (data['duration'] / 30)) * off_value
            #
            # # 判断余额是足购
            # if m.amount < need_money:
            #     return Response({
            #         'code': 2,
            #         'msg': 'user amount is not enough!',
            #     })

            data['user_id'] = req_user.id
            data['start_time'] = int(time.time())
            data['state'] = 'e'

            # 使用用户key创建bucket
            s3 = init_s3_connection(req_user.profile.access_key, req_user.profile.secret_key)
            s3.create_bucket(Bucket=data['name'])

            # 利用管理员key为新创建的bucket设置配额
            # rgw = init_rgw_api()
            # rgw.set_bucket_quota(
            #     req_user.username,
            #     bucket=data['name'],
            #     # max_size_kb=data['capacity'] * 1024 * 1024,
            #     enabled=True
            # )
            # -------- ceph bucket成功创建 ---------

            # 本地数据库插入记录
            model.objects.create(**data)
            # 更新优惠码
            # if off_code:
            #     update_off_code(off_code)
            # # 更新用户余额
            # m.cost(data['capacity'] * price * (data['duration'] / 30))
            status_code = HTTP_201_CREATED

        # 目前仅支持修改bucket可用时长
        # if request.method == 'PUT':
        #     b = model.objects.select_related('bucket_type').get(pk=data['bucket_id'])
        #     m = Money.objects.get(user=req_user.id)
        #     # 价格
        #     price = b.bucket_type.price
        #     # 用户额
        #     amount = m.amount
        #
        #     off_value = 1
        #     off_code = None
        #     if 'offset_code' in data:
        #         off_code = data['offset_code']
        #         off_value = get_offset_value(off_code)
        #         del data['offset_code']
        #
        #     # 原始续期空间大小*续期时长（月）*价格*优惠折扣
        #     need_money = (b.capacity * (data['duration'] / 30) * price) * off_value
        #     # 余额不足
        #     if need_money > amount:
        #         return Response({
        #             'code': 2,
        #             'msg': 'user amount is not enough'
        #         }, status=HTTP_400_BAD_REQUEST)
        #
        #     # 更新用户到期时间和开始计费时间
        #     b.renewal(data['duration'])
        #     # 更新用户余额
        #     m.cost(need_money)
        #     # 更新折扣码，使用次数+1
        #     if off_code:
        #         update_off_code(data['offset_code'])
        #     status_code = HTTP_200_OK

        if request.method == 'DELETE':
            # 即不是超级管理员，也不是bucket拥有者，提示非异操作
            bucket = model.objects.get(pk=data['bucket_id'])
            if bucket.user != req_user and not req_user.is_superuser:
                return Response({
                    'code': 2,
                    'msg': 'illegal delete bucket'
                }, status=HTTP_400_BAD_REQUEST)

            # # 如果bucket未到期，非强制，不能删除，删除后不方便退费
            # force_delete = request.GET.get('force_delete', False)
            # if not bucket.check_bucket_expire() and force_delete != 'yes':
            #     return Response({
            #         'code': 2,
            #         'msg': 'bucket is not expire, can not delete'
            #     }, status=HTTP_400_BAD_REQUEST)

            status_code = HTTP_200_OK
            # ceph集群删除bucket
            rgw = init_rgw_api()
            rgw.remove_bucket(bucket=bucket.name, purge_objects=True)
            # 删除数据记录
            bucket.delete()

    except Exception as e:
        return Response({
            'code': 3,
            'msg': 'error, %s' % str(e)
        })

    return Response({
        'code': 0,
        'msg': 'success'
    }, status=status_code)


@api_view(('GET', ))
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
        b = Buckets.objects.get(name=bucket_name)
    except:
        b = None

    if not b or b.user != req_user or not req_user.is_superuser:
        return Response({
            'code': 1,
            'msg': 'not found this bucket'
        }, status=HTTP_400_BAD_REQUEST)

    try:
        rgw = init_rgw_api()
        data = rgw.get_bucket(bucket=bucket_name)
    except Exception as e:
        return Response({
            'code': 1,
            'msg': 'get bucket detail failed',
            'error': str(e)
        }, status=HTTP_400_BAD_REQUEST)

    return Response({
        'code': 0,
        'msg': 'success',
        'data': data
    })


def query_bucket_exist(name):
    try:
        Buckets.objects.get(name=name)
    except:
        return False
    else:
        return True


def get_offset_value(code):
    try:
        v = Offset.objects.get(code=code)
    except:
        return False
    else:
        return v.get_offset_value()


def update_off_code(code):
    v = Offset.objects.get(code=code)
    v.use_offset_code()
