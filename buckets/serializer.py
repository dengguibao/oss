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
    en_status = SerializerMethodField()
    bucket_region = BucketRegionSerialize(read_only=True)
    cn_permission = SerializerMethodField()
    en_permission = SerializerMethodField()

    def get_cn_status(self, obj):
        s, _ = self.get_status(obj)
        return s

    def get_en_status(self, obj):
        _, s = self.get_status(obj)
        return s

    def get_status(self, obj):
        if obj.state == 'e':
            return '启用', 'enable'
        if obj.state == 'd':
            return '停用', 'disable'
        if obj.state == 's':
            return '暂停', 'suspend'

    def bucket_all_permission(self):
        return BucketAcl.objects.all()

    def get_cn_permission(self, obj):
        s, _ = self.get_permission(obj)
        return s

    def get_en_permission(self, obj):
        _, s = self.get_permission(obj)
        return s

    def get_permission(self, obj):
        data = {
            'private': '私有',
            'public-read': '公开读',
            'public-read-write': '公开读写',
            'authenticated': '授权读写'
        }
        return data[obj.permission] if obj.permission in data else 'unknow', obj.permission

    class Meta:
        model = Buckets
        fields = (
            'bucket_id', "name", "state", "user", "profile", 'cn_status',
            'create_time', 'bucket_region', 'cn_permission', 'en_permission',
            'version_control', 'en_status',

        )

        # read_only_fields = (
        #     'bucket_id', 'user', 'state', 'create_time',
        #     'profile', 'bucket_type'
        # )
