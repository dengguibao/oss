from .models import Buckets, BucketType, BucketRegion, BucketAcl
from rest_framework.serializers import ModelSerializer, SerializerMethodField
from user.serializer import UserSerialize, ProfileSerialize


class BucketTypeSerialize(ModelSerializer):
    class Meta:
        model = BucketType
        fields = (
            "name",
        )


class BucketRegionSerialize(ModelSerializer):
    class Meta:
        model = BucketRegion
        fields = (
            'name',
        )


class SimpleBucketSerialize(ModelSerializer):
    class Meta:
        model = Buckets
        fields = (
            "name",
        )


class BucketSerialize(ModelSerializer):
    user = UserSerialize(read_only=True)
    profile = ProfileSerialize(read_only=True)
    cn_status = SerializerMethodField()
    bucket_region = BucketRegionSerialize(read_only=True)
    permission = SerializerMethodField()

    def get_cn_status(self, obj):
        if obj.state == 'e':
            return '启用'
        if obj.state == 'd':
            return '停用'
        if obj.state == 's':
            return '暂停'
        return ''

    def bucket_all_permission(self):
        return BucketAcl.objects.all()

    def get_permission(self, obj):
        all_perm = self.bucket_all_permission()
        acl = 'private'
        for i in all_perm:
            if i.bucket_id == obj.bucket_id:
                acl = i.permission
                break

        data = {
            'private': '私有',
            'public-read': '公开读',
            'public-read-write': '公开读写',
            'authenticated-read': '认证读'
        }
        return data[acl] if acl in data else 'unknow'

    class Meta:
        model = Buckets
        fields = (
            'bucket_id',
            "name", "capacity", "duration",
            "start_time", "state", "user",
            "profile", 'cn_status', 'create_time',
            'bucket_region', 'permission', 'version_control'
        )

        # read_only_fields = (
        #     'bucket_id', 'user', 'state', 'create_time',
        #     'profile', 'bucket_type'
        # )
