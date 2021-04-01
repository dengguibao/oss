from rest_framework.serializers import ModelSerializer
from django.contrib.auth.models import User
from .models import Profile


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


class UserSerialize(ModelSerializer):
    profile = ProfileSerialize(read_only=True)
    # profile = PrimaryKeyRelatedField(read_only=True)


    class Meta:
        model = User
        fields = ('id', 'is_superuser', 'username', 'is_active', 'first_name', 'last_login', 'date_joined', 'email', 'profile')
