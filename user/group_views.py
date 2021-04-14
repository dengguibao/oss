from django.contrib.auth.models import Group, User, Permission

from rest_framework.exceptions import ParseError, NotAuthenticated, NotFound
from rest_framework.response import Response
from rest_framework.status import HTTP_201_CREATED
from rest_framework.views import APIView
from rest_framework.decorators import api_view

from common.verify import verify_max_length, verify_in_array
from common.func import verify_super_user, clean_post_data

all_perms = {
    "auth.view_user": "获取用户详情",
    "auth.delete_user": "删除用户",
    "user.add_quota": "购买存储容量",
    "user.change_quota": "扩容及续费存储容量",
    "buckets.add_bucketregion": "新增存储区域",
    "buckets.change_bucketregion": "修改存储区域",
    "buckets.view_bucketregion": "查看存储区域",
    "buckets.delete_bucketregion": "删除存储区域",
    "buckets.view_buckets": "查看bucket",
    "buckets.add_buckets": "新增bucket",
    "buckets.delete_buckets": "删除bucket",
    "buckets.change_buckets": "修改bucket读写权限",
    "buckets.add_bucketacl": "添加bucket授权",
    "buckets.view_bucketacl": "删除bucket授权",
    "buckets.delete_bucketacl": "修改bucket授权",
    "objects.change_objects": "修改文件对象的读写权限",
    "objects.view_objects": "查看文件对象的读写权限",
    "objects.add_objectacl": "添加文件对象授权",
    "objects.delete_objectacl": "删除文件对象授权",
    "objects.view_objectacl": "列出文件对象授权",
}


@api_view(('GET',))
def list_all_available_perms_endpoint(request):
    return Response({
        'code': 0,
        'msg': 'success',
        'data': all_perms
    })


class SetGroupEndpoint(APIView):

    def get(self, request):
        """
        查询所有可用的角色（组）
        """
        verify_super_user(request)
        ret = Group.objects.prefetch_related('permissions').prefetch_related('user_set__groups').all()
        data = []
        for i in ret:
            data.append({
                'id': i.id,
                'name': i.name,
                'permissions': i.permissions.all().values('codename', 'name'),
                'users': i.user_set.all().values('username', 'first_name')
            })
        return Response({
            'code': 0,
            'msg': 'success',
            'data': data
        })

    def post(self, request):
        """
        新增一个角色
        """
        verify_super_user(request)
        fields = [
            ('*name', str, (verify_max_length, 20))
        ]
        data = clean_post_data(request.body, fields)
        Group.objects.update_or_create(
            name=data['name']
        )

        return Response({
            'code': 0,
            'msg': 'success',
            # 'data': model_to_dict(g)
        }, status=HTTP_201_CREATED)

    def delete(self, request):
        """
        删除一个角色
        """
        verify_super_user(request)
        id = request.GET.get('id', None)
        try:
            g = Group.objects.get(id=int(id))
        except TypeError:
            raise ParseError('id is not a number')
        except Group.DoesNotExist:
            raise NotFound('not found this group')
        g.delete()
        return Response({
            'code': 0,
            'msg': 'success'
        })


class SetGroupPermissionEndpoint(APIView):

    def get(self, request):
        """
        查询某个用户的权限
        """
        username = request.GET.get('username', None)

        try:
            perm_list = []
            if username:
                u = User.objects.get(username=username)
                perm_list = u.get_all_permissions()

        except User.DoesNotExist:
            raise NotFound('not fount this user')

        except Exception as e:
            raise ParseError(str(e))

        return Response({
            'code': 0,
            'msg': 'success',
            'data': perm_list
        })

    def post(self, request):
        """
        将权限授权给某个角色（组）
        """
        data = self.check_post_data(request)
        perm = data['perm']
        try:
            g = Group.objects.get(name=data['role'])
        except Group.DoesNotExist:
            raise NotFound('not found this group')
        perm_obj = self.get_perm_obj(perm)
        g.permissions.add(perm_obj)
        return Response({
            'code': 0,
            'msg': 'success'
        })

    def delete(self, request):
        """
        将权限从某个角色（组）中移除
        """
        data = self.check_post_data(request)
        perm = data['perm']
        try:
            g = Group.objects.get(name=data['role'])
        except Group.DoesNotExist:
            raise NotFound('not found this group')
        perm_obj = self.get_perm_obj(perm)

        g.permissions.remove(perm_obj)
        return Response({
            'code': 0,
            'msg': 'success'
        })

    @staticmethod
    def check_post_data(request):
        fields = [
            ('*role', str, (verify_max_length, 20)),
            ('*perm', str, (verify_in_array, all_perms.keys()))
        ]
        return clean_post_data(request.body, tuple(fields))

    def get_perm_obj(self, perm_name):
        return Permission.objects.get(codename=perm_name.split('.')[1])


class SetGroupMemberEndpoint(APIView):

    def post(self, request):
        """
        将用户添加进某个角色（组）
        """
        data = self.check_post(request)
        try:
            g = Group.objects.get(name=data['role'])
            u = User.objects.get(username=data['username'])
        except Group.DoesNotExist:
            raise NotFound('not found this group')
        except User.DoesNotExist:
            raise NotFound('not found this user')

        g.user_set.add(u)
        return Response({
            'code': 0,
            'msg': 'success'
        })

    def delete(self, request):
        """
        将用户从某个角色（组）移除
        """
        data = self.check_post(request)
        try:
            g = Group.objects.get(name=data['role'])
            u = User.objects.get(username=data['username'])
        except Group.DoesNotExist:
            raise NotFound('not found this group')
        except User.DoesNotExist:
            raise NotFound('not found this user')

        g.user_set.remove(u)
        return Response({
            'code': 0,
            'msg': 'success'
        })

    @staticmethod
    def check_post(request):
        fields = [
            ('*role', str, (verify_max_length, 20)),
            ('*username', str, (verify_max_length, 20))
        ]
        return clean_post_data(request.body, tuple(fields))