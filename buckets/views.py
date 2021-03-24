from django.shortcuts import render
from .models import BucketType, Buckets, Offset
from django.contrib.auth.models import User
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_201_CREATED, HTTP_403_FORBIDDEN
from common.verify import verify_max_length, verify_body, verify_field, verify_length
from common.func import init_s3_connection


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
        ('*price', float, (verify_max_length, 5))
    ]
    id_field = (('*bucket_type_id', int, (verify_max_length, 9)),)

    if request.method == 'GET':
        # id = request.GET.get('id', None)
        # if id:
        #     try:
        #         result = model.objects.get(pk=int(id))
        #     except:
        #         return Response({
        #             'code': 1,
        #             'msg': 'success',
        #             'data': 'error id'
        #         }, status=HTTP_400_BAD_REQUEST)
        # else:
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
                'code': 1,
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
            'code': 1,
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
        ('*offset', float, (verify_max_length, 4)),
        ('*max_use_times', int, (verify_max_length, 5)),
        ('*valid_days', int, (verify_max_length, 3)),
    ]
    id_field = (('*off_id', int, (verify_max_length, 10)),)

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
                }, status=HTTP_400_BAD_REQUEST)
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
                'code': 1,
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
            'code': 1,
            'msg': 'error, %s' % e.args
        }, status=HTTP_400_BAD_REQUEST)
    else:
        return Response({
            'code': 0,
            'msg': 'success'
        }, status=status_code)



