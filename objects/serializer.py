from rest_framework.serializers import ModelSerializer, SerializerMethodField
from buckets.serializer import SimpleBucketSerialize
from user.serializer import SimpleUserSerialize
from .models import Objects
import base64


class ObjectsSerialize(ModelSerializer):
    owner = SimpleUserSerialize(read_only=True)
    bucket = SimpleBucketSerialize(read_only=True)
    # type = SerializerMethodField()
    cn_type = SerializerMethodField()
    key_url = SerializerMethodField()
    # root_url = SerializerMethodField()
    cn_permission = SerializerMethodField()
    root = SerializerMethodField()


    # def get_type(self, obj):
    #     return 'File' if obj.type == 'f' else 'Directory'

    def get_root(self, obj):
        return obj.root if obj.root else '/'

    def get_key_url(self, obj):
        return base64.urlsafe_b64encode(obj.key.encode())
        # return obj.key.replace('/', ',')

    def get_cn_type(self, obj):
        if obj.type == 'd':
            return "文件夹"
        if obj.type == 'f':
            return "文件"
        return "未知"

    def get_cn_permission(self, obj):
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
            'upload_time', "cn_type", 'key_url',
            'permission', 'cn_permission'
        )
