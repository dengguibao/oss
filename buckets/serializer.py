from .models import Buckets, BucketType
from rest_framework.serializers import ModelSerializer, SerializerMethodField
from user.serializer import UserSerialize, ProfileSerialize


class BucketTypeSerialize(ModelSerializer):
    class Meta:
        model = BucketType
        fields = (
            'name', 'price'
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
    bucket_type = BucketTypeSerialize(read_only=True)
    cn_status = SerializerMethodField()

    def get_cn_status(self, obj):
        if obj.state == 'e':
            return '启用'
        if obj.state == 'd':
            return '停用'
        if obj.state == 's':
            return '暂停'
        return ''

    class Meta:
        model = Buckets
        fields = (
            "name", "capacity", "duration",
            "start_time", "state", "user",
            "profile", "bucket_type", 'bucket_id',
            'cn_status', 'create_time'
        )

        # read_only_fields = (
        #     'bucket_id', 'user', 'state', 'create_time',
        #     'profile', 'bucket_type'
        # )
