from rest_framework.serializers import ModelSerializer
from django.contrib.auth.models import User
from .models import Profile, Quota, Money


class ProfileSerialize(ModelSerializer):
    # profile = HyperlinkedRelatedField(read_only=True)

    class Meta:
        model = Profile
        fields = (
            'phone', 'phone_verify', 'is_subuser', 'ceph_uid', 'access_key', 'secret_key'
        )


class SimpleUserSerialize(ModelSerializer):
    class Meta:
        model = User
        fields = (
            'username', 'first_name'
        )


class QuotaSerialize(ModelSerializer):
    class Meta:
        model = Quota
        fields = '__all__'


class MoneySerialize(ModelSerializer):
    class Meta:
        model = Money
        fields = '__all__'


class UserSerialize(ModelSerializer):
    profile = ProfileSerialize(read_only=True)
    capacity = QuotaSerialize(read_only=True)

    class Meta:
        model = User
        fields = (
            'id', 'is_superuser', 'username',
            'is_active', 'first_name', 'last_login',
            'date_joined', 'email', 'profile', 'capacity'

        )


class UserDetailSerialize(ModelSerializer):
    profile = ProfileSerialize(read_only=True, allow_null=True)
    money = MoneySerialize(read_only=True, allow_null=True)
    quota = QuotaSerialize(read_only=True, allow_null=True)

    class Meta:
        model = User
        # fields = '__all__'
        exclude = ('password',)
