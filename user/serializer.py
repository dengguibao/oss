import time

from rest_framework.serializers import ModelSerializer, SerializerMethodField
from django.contrib.auth.models import User
from .models import Profile, CapacityQuota, BandwidthQuota, Keys


class ProfileSerialize(ModelSerializer):

    class Meta:
        model = Profile
        fields = '__all__'


class KeysSerialize(ModelSerializer):

    class Meta:
        model = Keys
        fields = (
            'ceph_uid', 'user_access_key', 'user_secret_key'
        )


class BandwidthSerialize(ModelSerializer):
    deadline = SerializerMethodField()
    expired = SerializerMethodField()

    def get_expired(self, obj):
        return True if obj.valid() is False else False

    def get_deadline(self, obj):
        ts = time.localtime(obj.start_time+(obj.duration*86400))
        return time.strftime('%F %T', ts)

    class Meta:
        model = BandwidthQuota
        fields = '__all__'


class CapacityQuotaSerialize(ModelSerializer):

    deadline = SerializerMethodField()
    expired = SerializerMethodField()

    def get_expired(self, obj):
        return True if obj.valid() is False else False


    def get_deadline(self, obj):
        ts = time.localtime(obj.start_time + (obj.duration * 86400))
        return time.strftime('%F %T', ts)

    class Meta:
        model = CapacityQuota
        fields = '__all__'


class SimpleUserSerialize(ModelSerializer):
    class Meta:
        model = User
        fields = (
            'username', 'first_name'
        )


class UserSerialize(ModelSerializer):
    profile = ProfileSerialize(read_only=True)
    capacity_quota = CapacityQuotaSerialize(read_only=True)
    # keys = KeysSerialize()
    bandwidth_quota = BandwidthSerialize()

    class Meta:
        model = User
        fields = (
            'id', 'is_superuser', 'username', 'is_active', 'first_name', 'last_login',
            'date_joined', 'email', 'profile', 'capacity_quota', 'bandwidth_quota'

        )


class UserDetailSerialize(ModelSerializer):
    profile = ProfileSerialize(read_only=True)
    capacity_quota = CapacityQuotaSerialize(read_only=True)
    keys = KeysSerialize()
    bandwidth_quota = BandwidthSerialize()

    class Meta:
        model = User
        # fields = '__all__'
        exclude = ('password',)
