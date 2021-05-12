from django.contrib.auth.models import User
from rest_framework.exceptions import ParseError, NotAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_201_CREATED
from rest_framework.views import APIView
from rest_framework.permissions import DjangoModelPermissions

from buckets.models import BucketAcl, Buckets
from common.func import validate_post_data
from common.verify import verify_pk, verify_in_array, verify_username


class BucketAclEndpoint(APIView):
    model = BucketAcl
    queryset = model.objects.none()
    permission_classes = (DjangoModelPermissions,)

    def get(self, request):
        bid = request.GET.get('bucket_id', None)
        try:
            b = Buckets.objects.get(bucket_id=int(bid))
            self.queryset = self.model.objects.select_related('user').select_related('bucket').filter(bucket=b).values(
                'user__first_name', 'user__username', 'bucket__name', 'permission', 'acl_bid'
            )
        except Buckets.DoesNotExist:
            raise ParseError('not found this bucket')
        except self.model.DoesNotExist:
            raise ParseError('not found resource')
        except TypeError:
            raise ParseError('arg acl_bid is not a number')

        if b.user != request.user:
            raise NotAuthenticated('user and bucket__user not match')

        return Response({
            'code': 0,
            'msg': 'success',
            'data': list(self.queryset)
        })

    def post(self, request):
        fields = (
            ('*bucket_id', int, (verify_pk, Buckets)),
            ('*username', str, verify_username),
            ('*permission', str, (verify_in_array, ('authenticated-read', 'authenticated-read-write')))
        )
        data = validate_post_data(request.body, fields)
        try:
            bucket = Buckets.objects.get(bucket_id=int(data['bucket_id']))
            user = User.objects.get(username=data['username'])
        except Buckets.DoesNotExist:
            raise ParseError('not found this bucket')
        except User.DoesNotExist:
            raise ParseError('not found this user')

        if user.profile.root_uid != request.user.username and user.profile.parent_uid != request.user.username:
            raise ParseError('only support authorized to sub user')

        if request.user != bucket.user:
            raise ParseError('bucket owner and user not match')

        self.queryset, created = self.model.objects.update_or_create(
            bucket=bucket,
            user=user,
            permission=data['permission']
        )

        return Response({
            'code': 0,
            'msg': 'success',
            'data': self.queryset.json
        }, status=HTTP_201_CREATED)

    def delete(self, request):
        acl_bid = request.GET.get('acl_bid', None)

        try:
            self.queryset = self.model.objects.get(acl_bid=int(acl_bid))
        except self.model.DoesNotExist:
            raise ParseError('not found resource')
        except TypeError:
            raise ParseError('arg acl_bid is not a number')

        if self.queryset.bucket.user != request.user:
            raise NotAuthenticated('user and bucket owner not match')

        self.queryset.delete()
        return Response({
            'code': 0,
            'msg': 'success'
        })
