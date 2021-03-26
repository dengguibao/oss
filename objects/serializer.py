from rest_framework.serializers import ModelSerializer
from buckets.serializer import SimpleBucketSerialize
from user.serializer import SimpleUserSerialize
from .models import Objects


class ObjectsSerialize(ModelSerializer):
    owner = SimpleUserSerialize(read_only=True)
    bucket = SimpleBucketSerialize(read_only=True)

    class Meta:
        model = Objects
        field = (
            'name', 'bucket', 'obj_id', 'type',
            'root', 'file_size', 'md5', 'etag', 'owner',
            'upload_time'
        )
