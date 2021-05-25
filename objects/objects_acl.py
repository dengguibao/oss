from django.contrib.auth.models import User
from rest_framework.exceptions import ParseError, NotAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_201_CREATED
from rest_framework.views import APIView
from rest_framework.permissions import DjangoModelPermissions

from common.func import validate_post_data
from common.verify import verify_pk, verify_username, verify_in_array
from objects.models import Objects, ObjectAcl
from objects.objects_perms import verify_file_owner_and_permission, PermAction


class ObjectAclEndpoint(APIView):
    model = ObjectAcl
    permission_classes = (DjangoModelPermissions,)
    queryset = model.objects.none()

    def get(self, request):
        bid = request.GET.get('obj_id', None)
        try:
            self.queryset = Objects.objects.get(obj_id=int(bid))
            res = ObjectAcl.objects.select_related('user').filter(object=self.queryset).values(
                'user__first_name', 'user__username', 'permission', 'acl_oid', 'object__name'
            )
        except Objects.DoesNotExist:
            raise ParseError('not found this file object')
        except ObjectAcl.DoesNotExist:
            raise ParseError('not found object acl')

        return Response({
            'code': 0,
            'msg': 'success',
            'data': list(res)
        })

    def post(self, request):
        fields = (
            ('*obj_id', int, (verify_pk, Objects)),
            ('*username', str, verify_username),
            ('*permission', str, (verify_in_array, ('authenticated-read', 'authenticated-read-write')))
        )
        data = validate_post_data(request.body, fields)
        try:
            self.queryset = Objects.objects.get(obj_id=int(data['obj_id']))
            authorize_user = User.objects.get(username=data['username'])
        except Objects.DoesNotExist:
            raise ParseError('not found this bucket')
        except User.DoesNotExist:
            raise ParseError('not found this user')

        if authorize_user.profile.root_uid != request.user.username and \
                authorize_user.profile.parent_uid != request.user.username:
            raise ParseError('only support authorized to sub user')

        verify_file_owner_and_permission(request, PermAction.RW, self.queryset)

        ObjectAcl.objects.update_or_create(
            object=self.queryset,
            user=authorize_user,
            permission=data['permission']
        )

        return Response({
            'code': 0,
            'msg': 'success',
            'data': self.queryset.json
        }, status=HTTP_201_CREATED)

    def delete(self, request):
        acl_oid = request.GET.get('acl_oid', None)

        try:
            self.queryset = ObjectAcl.objects.get(acl_oid=int(acl_oid))
        except ObjectAcl.DoesNotExist:
            raise ParseError('not found resource')
        except TypeError:
            raise ParseError('acl_oid is not a number')

        verify_file_owner_and_permission(request, PermAction.RW, self.queryset)

        self.queryset.delete()

        return Response({
            'code': 0,
            'msg': 'success'
        })
