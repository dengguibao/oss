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
    en_product = SerializerMethodField()

    def get_cn_product(self, obj):
        return '存储' if obj.product == 's' else '带宽'

    def get_en_product(self, obj):
        return 'Storage' if obj.product == 's' else 'Bandwidth'

    class Meta:
        model = Order
        fields = '__all__'
