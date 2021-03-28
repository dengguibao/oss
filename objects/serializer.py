from rest_framework.serializers import ModelSerializer, SerializerMethodField
from buckets.serializer import SimpleBucketSerialize
from user.serializer import SimpleUserSerialize
from .models import Objects


class ObjectsSerialize(ModelSerializer):
    owner = SimpleUserSerialize(read_only=True)
    bucket = SimpleBucketSerialize(read_only=True)
    cn_type = SerializerMethodField()

    def get_cn_type(self,obj):
        if obj.type == 'd':
            return "文件夹"
        if obj.type == 'f':
            return "文件"
        return "未知"

    class Meta:
        model = Objects
        fields = (
            'name', 'bucket', 'obj_id', 'type',
            'root', 'file_size', 'md5', 'etag', 'owner',
            'upload_time', "cn_type"
        )
