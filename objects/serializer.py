from rest_framework.serializers import ModelSerializer, SerializerMethodField
from buckets.serializer import SimpleBucketSerialize
from user.serializer import SimpleUserSerialize
from .models import Objects
import base64


class ObjectsSerialize(ModelSerializer):
    owner = SimpleUserSerialize(read_only=True)
    bucket = SimpleBucketSerialize(read_only=True)
    cn_type = SerializerMethodField()
    key_url = SerializerMethodField()
    root_url = SerializerMethodField()
    permission = SerializerMethodField()

    def get_root_url(self, obj):
        return obj.root.replace('/', ',') if obj.root else None

    def get_key_url(self, obj):
        return base64.urlsafe_b64encode(obj.key.encode())
        # return obj.key.replace('/', ',')

    def get_cn_type(self, obj):
        if obj.type == 'd':
            return "文件夹"
        if obj.type == 'f':
            return "文件"
        return "未知"

    def get_permission(self, obj):
        data = {
            'private': '私有',
            'public-read': '公开读',
            'public-read-write': '公开读写',
            'authenticated': '授权读写'
        }
        return data[obj.permission] if obj.permission in data else 'unknow'

    class Meta:
        model = Objects
        fields = (
            'name', 'bucket', 'obj_id', 'type',
            'root', 'file_size', 'md5', 'etag', 'owner',
            'upload_time', "cn_type", 'key', 'key_url',
            'root_url', 'permission'
        )
