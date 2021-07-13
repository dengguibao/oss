from django.contrib.auth.models import Group, User, Permission

from rest_framework.exceptions import ParseError, NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.status import HTTP_201_CREATED
from rest_framework.views import APIView
from rest_framework.decorators import api_view
from rest_framework.permissions import DjangoModelPermissions

from common.verify import verify_max_length, verify_in_array, verify_pk
from common.func import verify_super_user, validate_post_data

all_perms = [
    {
        'title': 'User',
        'key': '0-0',
        'children': [
            {
                'title': "查看用户详情及用量",
                'key': "auth.view_user"
            },
            {
                'title': "修改密码",
                'key': "auth.change_user"
            },
            {
                'title': "删除用户",
                'key': "auth.delete_user"
            },
            {
                'title': "更换key与设置使用白名单",
                'key': "user.change_keys"
            }
        ]
    },
    {
        'title': 'Quota',
        'key': '0-1',
        'children': [
            {
                'title': "购买存储容量",
                'key': "user.add_capacityquota"
            },
            {
                'title': "续费存储容量",
                'key': "user.change_capacityquota"

            },
            {
                'title': "购买下载带宽",
                'key': "user.add_bandwidthquota"

            },
            {
                'title': "续费下载带宽",
                'key': "user.change_bandwidthquota"
            }
        ]
    },
    {
        'title': 'Bucket',
        'key': '0-2',
        'children': [
            {
                'title': "创建bucket",
                'key': "buckets.add_buckets"
            },
            {
                'title': "删除bucket",
                'key': "buckets.delete_buckets"
            },
            {
                'title': "bucket备份与权限修改",
                'key': "buckets.change_buckets"
            },
            {
                'title': "添加bucket授权",
                'key': "buckets.add_bucketacl"
            },
            {
                'title': "删除bucket授权",
                'key': "buckets.delete_bucketacl"
            },
        ]
    },
    {
        'title': 'Object',
        'key': '0-3',
        'children': [
            {
                'title': "设置文件对象的访问权限",
                'key': "objects.change_objects"
            },
            {
                'title': "查看文件对象的访问权限",
                'key': "objects.view_objects"
            },
            {
                'title': "设置文件对象授权",
                'key': "objects.add_objectacl"
            },
            {
                'title': "删除对文件对象的授权",
                'key': "objects.delete_objectacl"
            },
        ]
    },
    {
        'title': 'Region',
        'key': '0-4',
        'children': [
            {
                'title': "新增存储区域",
                'key': "buckets.add_bucketregion"
            },
            {
                'title': "修改存储区域",
                'key': "buckets.change_bucketregion"
            },
            {
                'title': "删除存储区域",
                'key': "buckets.delete_bucketregion"
            }
        ]
    },
    {
        'title': 'Plan',
        'key': '0-5',
        'children': [
            {
                'title': "新增套餐与定价",
                'key': "account.add_plan"
            },
            {
                'title': "修改套餐与定价",
                'key': "account.change_plan"
            },
            {
                'title': "删除套餐与定价",
                'key': "account.delete_plan"
            },

        ]
    },
]


def build_cn_permission_list(user_perms, _type: str = 'long'):
    data = []
    for i in all_perms:
        for c in i['children']:
            title, key = c.values()
            for p in user_perms:
                if p in key:
                    data.append({
                            'key': key,
                            'label': title
                    })
    return data


@api_view(('GET',))
def list_all_available_perms_endpoint(request):
    return Response({
        'code': 0,
        'msg': 'success',
        'data': all_perms
    })


@api_view(('PUT',))
def set_default_user_role(request):
    if not request.user.is_superuser:
        raise PermissionDenied()

    fields = (
        ('*group_id', int, (verify_pk, Group)),
    )
    data = validate_post_data(request.body, fields)
    group = Group.objects.get(pk=data['group_id'])
    group.default_group.set_default()
    return Response({
        'code': 0,
        'msg': 'success'
    })


class GroupEndpoint(APIView):
    queryset = Group.objects.none()

    def get(self, request):
        """
        查询所有可用的角色（组）
        """
        if not request.user.has_perm('auth.view_group'):
            raise PermissionDenied()

        role_name = request.GET.get('name', None)
        data_source = Group.objects.prefetch_related('permissions').prefetch_related('user_set__groups')
        if role_name:
            self.queryset = data_source.filter(name=role_name)
        else:
            self.queryset = data_source.all()

        data = []
        for i in self.queryset:
            data.append({
                'id': i.id,
                'name': i.name,
                'default': i.default_group.default,
                'permissions': build_cn_permission_list(
                    [p.codename for p in i.permissions.all()], 'short'
                ),
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
        fields = [
            ('*name', str, (verify_max_length, 20))
        ]
        data = validate_post_data(request.body, fields)
        self.queryset, _ = Group.objects.update_or_create(
            name=data['name']
        )

        return Response({
            'code': 0,
            'msg': 'success',
        }, status=HTTP_201_CREATED)

    def delete(self, request):
        """
        删除一个角色
        """
        group_id = request.GET.get('id', None)
        try:
            self.queryset = Group.objects.get(pk=int(group_id))
        except TypeError:
            raise ParseError('id is not a number')
        except Group.DoesNotExist:
            raise NotFound('not found this group')
        self.queryset.delete()
        return Response({
            'code': 0,
            'msg': 'success'
        })


class GroupPermissionEndpoint(APIView):
    queryset = Group.objects.none()
    permission_classes = (DjangoModelPermissions,)

    def get(self, request):
        """
        查询某个用户的权限
        """
        username = request.GET.get('username', None)

        try:
            perm_list = []
            if username:
                self.queryset = User.objects.get(username=username)
                perm_list = self.queryset.get_all_permissions()

        except User.DoesNotExist:
            raise NotFound('not fount this user')

        except Exception as e:
            raise ParseError(str(e))

        return Response({
            'code': 0,
            'msg': 'success',
            'data': build_cn_permission_list(perm_list)
        })

    def post(self, request):
        """
        将权限授权给某个角色（组）
        """
        group, perms = self.get_group_and_permission(request)
        for p in perms:
            group.permissions.add(p)
        return Response({
            'code': 0,
            'msg': 'success'
        })

    def delete(self, request):
        """
        将权限从某个角色（组）中移除
        """
        group, perms = self.get_group_and_permission(request)
        for p in perms:
            group.permissions.remove(p)
        return Response({
            'code': 0,
            'msg': 'success'
        })

    @staticmethod
    def get_group_and_permission(request):
        fields = [
            ('*role', str, (verify_max_length, 20)),
            ('*perms', list, len)
        ]
        data = validate_post_data(request.body, tuple(fields))

        try:
            group = Group.objects.get(name=data['role'])
        except Group.DoesNotExist:
            raise NotFound('not found this group')

        perms = []
        for p in data['perms']:
            try:
                perm = Permission.objects.get(codename=p.split('.')[1])
            except Permission.DoesNotExist:
                continue
                # raise NotFound('not found this permission object')
            else:
                perms.append(perm)

        return group, perms


class GroupMemberEndpoint(APIView):
    queryset = Group.objects.none()
    permission_classes = (DjangoModelPermissions,)

    def post(self, request):
        """
        将用户添加进某个角色（组）
        """
        group, user = self.get_group_and_member(request)

        group.user_set.add(user)
        return Response({
            'code': 0,
            'msg': 'success'
        })

    def delete(self, request):
        """
        将用户从某个角色（组）移除
        """
        group, user = self.get_group_and_member(request)

        group.user_set.remove(user)
        return Response({
            'code': 0,
            'msg': 'success'
        })

    @staticmethod
    def get_group_and_member(request):
        fields = [
            ('*role', str, (verify_max_length, 20)),
            ('*username', str, (verify_max_length, 20))
        ]
        data = validate_post_data(request.body, tuple(fields))
        try:
            g = Group.objects.get(name=data['role'])
            u = User.objects.get(username=data['username'])
        except Group.DoesNotExist:
            raise NotFound('not found this group')
        except User.DoesNotExist:
            raise NotFound('not found this user')
        return g, u
