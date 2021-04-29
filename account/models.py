from django.db import models
from django.contrib.auth.models import User
from django.dispatch import receiver
import time
import random
from user.signal import create_order


class Plan(models.Model):
    STATE = (
        ('e', 'enable'),
        ('d', 'disable'),
    )
    name = models.CharField(verbose_name='plan name', max_length=50, blank=False)
    s_price = models.FloatField(verbose_name='storage price', blank=False, null=False)
    b_price = models.FloatField(verbose_name='bandwidth price', blank=False, null=False)
    state = models.CharField(choices=STATE, max_length=1, blank=False)
    offset = models.FloatField(verbose_name='offset', default=1.0)
    offset_min_days = models.IntegerField(verbose_name='offset mini days', blank=True, default=0)
    plan_min_days = models.IntegerField(verbose_name='plan mini days', blank=True, default=0)
    pub_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def json(self):
        return {
            'name': self.name,
            's_price': self.s_price,
            'b_price': self.b_price,
            'state': self.get_state_display(),
            'offset': self.offset,
            'offset_min_days': self.offset_min_days,
            'plan_min_days': self.plan_min_days,
            'pub_date': self.pub_date
        }


class Order(models.Model):
    PRODUCT = (
        ('s', 'Storage'),
        ('b', 'Bandwidth'),
    )
    no = models.CharField(max_length=20, verbose_name='order no.', blank=False, null=False)
    create_date = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_order')
    product = models.CharField(max_length=1, choices=PRODUCT)
    plan = models.ForeignKey(Plan, models.SET_NULL, null=True, related_name='order_plan')
    detail = models.CharField(max_length=200, blank=True)
    pay = models.FloatField(null=False, blank=False)
    real_pay = models.FloatField(null=False, blank=False)

    class Meta:
        ordering = ['create_date']

    def __str__(self):
        return self.no


@receiver(create_order)
def create_order(sender, **kwargs):
    return Order.objects.create(
        no=build_order_no(),
        user_id=kwargs['user_id'],
        product=kwargs['product'],
        detail=kwargs['detail'],
        pay=kwargs['pay'],
        real_pay=kwargs['real_pay'],
        plan_id=kwargs['plan_id']
    )


def build_order_no():
    dt = time.strftime('%Y%m', time.localtime())
    no = ''.join(random.sample('0123456789', 10))
    return '-'.join((dt, no))
