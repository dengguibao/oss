from rest_framework.serializers import ModelSerializer, SerializerMethodField
from user.serializer import SimpleUserSerialize
from .models import Order, Plan


class PlanSerialize(ModelSerializer):

    class Meta:
        model = Plan
        fields = '__all__'


class OrderSerialize(ModelSerializer):
    user = SimpleUserSerialize(read_only=True)
    plan = PlanSerialize(read_only=True)
    cn_product = SerializerMethodField()

    def get_cn_product(self, obj):
        return '存储' if obj.product == 's' else '带宽'

    class Meta:
        model = Order
        fields = '__all__'
