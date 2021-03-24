from django.db import models
from django.contrib.auth.models import User
import time


class BucketType(models.Model):
    bucket_type_id = models.IntegerField(primary_key=True, auto_created=True)
    name = models.CharField(verbose_name='bucket type name', unique=True, blank=False, max_length=20)
    price = models.FloatField(verbose_name="bucket price", blank=False)
    create_time = models.DateTimeField(auto_now=True)


class Buckets(models.Model):
    STATE = (
        ('e', 'enable'),
        ('d', 'disable'),
        ('s', 'suspend')
    )
    bucket_id = models.IntegerField(primary_key=True, auto_created=True)
    name = models.CharField(verbose_name='bucket name', unique=True, max_length=63, blank=False),
    capacity = models.IntegerField(verbose_name="capacity", blank=False),
    duration = models.IntegerField(verbose_name="duration", blank=False),
    user = models.ForeignKey(User, on_delete=models.CASCADE),
    start_time = models.IntegerField(verbose_name='start time')
    bucket_type = models.ForeignKey(BucketType, on_delete=models.SET_NULL, null=True, blank=True)
    state = models.CharField(verbose_name='state', max_length=1, blank=False)
    create_time = models.DateTimeField(auto_now=True)

    def calculate_cost(self, capacity):
        return self.bucket_type.price*capacity

    def renewal(self, days: int):
        new_start = (self.start_time+(86400*self.duration))
        self.duration = days
        self.start_time = new_start
        self.save()


class BucketAcl(models.Model):
    acl_id = models.IntegerField(primary_key=True, auto_created=True)
    read = models.BooleanField(verbose_name='readable')
    write = models.BooleanField(verbose_name='writeable')
    list = models.BooleanField(verbose_name='list able')
    bucket = models.ForeignKey(Buckets, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)


class Offset(models.Model):
    off_id = models.IntegerField(primary_key=True, auto_created=True)
    code = models.CharField(verbose_name='offset code', max_length=6, blank=False)
    offset = models.FloatField(verbose_name='offset value', blank=False)
    used_times = models.IntegerField(verbose_name='used times', blank=False, default=0)
    max_use_times = models.IntegerField(verbose_name='max use times', blank=False, default=0)
    valid_days = models.IntegerField(verbose_name='valid days', blank=False, default=0)
    create_time = models.DateTimeField(auto_now=True)

    def get_offset_value(self):
        if self.used_times < self.max_use_times or \
                self.create_time.timestamp()+(86400*self.valid_days) < time.time():
            self.used_times += 1
            self.save()
            return self.offset, 'ok'
        else:
            return 1, 'expire or used done'
