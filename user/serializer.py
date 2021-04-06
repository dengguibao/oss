from rest_framework.serializers import ModelSerializer, PrimaryKeyRelatedField
from django.contrib.auth.models import User
from .models import Profile, Capacity


class ProfileSerialize(ModelSerializer):
    # profile = HyperlinkedRelatedField(read_only=True)

    class Meta:
        model = Profile
        fields = (
            'phone', 'phone_verify', 'is_subuser', 'ceph_uid'
        )


class SimpleUserSerialize(ModelSerializer):
    class Meta:
        model = User
        fields = (
            'username', 'first_name'
        )


class CapacitySerialize(ModelSerializer):
    class Meta:
        model = Capacity
        fields = '__all__'


class UserSerialize(ModelSerializer):
    profile = ProfileSerialize(read_only=True)
    capacity = CapacitySerialize(read_only=True)

    class Meta:
        model = User
        fields = (
            'id', 'is_superuser', 'username',
            'is_active', 'first_name', 'last_login',
            'date_joined', 'email', 'profile', 'capacity'

        )
