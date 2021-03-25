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
    name = models.CharField(verbose_name='bucket name', unique=True, max_length=63, blank=False, null=True)
    capacity = models.IntegerField(verbose_name="capacity", default=0, blank=False)
    duration = models.IntegerField(verbose_name="duration", default=0, blank=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user', null=True, blank=True)
    start_time = models.IntegerField(verbose_name='start time', blank=False, default=0)
    bucket_type = models.ForeignKey(BucketType, on_delete=models.SET_NULL, null=True, blank=True, related_name='bucket_type')
    state = models.CharField(choices=STATE, verbose_name='state', max_length=1, blank=False)
    create_time = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def calculate_cost(self, capacity):
        return self.bucket_type.price*capacity

    def renewal(self, days: int):
        new_start = (self.start_time+(86400*self.duration))
        self.duration = days
        self.start_time = new_start
        self.save()

    def check_bucket_expire(self):
       return True if self.start_time+self.duration*86400 > time.time() else False


class BucketAcl(models.Model):
    acl_id = models.IntegerField(primary_key=True, auto_created=True)
    read = models.BooleanField(verbose_name='readable')
    write = models.BooleanField(verbose_name='writeable')
    list = models.BooleanField(verbose_name='list able')
    bucket = models.ForeignKey(Buckets, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)


class Offset(models.Model):
    off_id = models.IntegerField(primary_key=True, auto_created=True)
    code = models.CharField(verbose_name='offset code', unique=True, max_length=6, blank=False)
    offset = models.FloatField(verbose_name='offset value', blank=False)
    used_times = models.IntegerField(verbose_name='used times', blank=False, default=0)
    max_use_times = models.IntegerField(verbose_name='max use times', blank=False, default=0)
    valid_days = models.IntegerField(verbose_name='valid days', blank=False, default=0)
    create_time = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code

    def get_offset_value(self):
        if self.used_times < self.max_use_times or \
                self.create_time.timestamp()+(86400*self.valid_days) < time.time():
            return self.offset
        else:
            return 1

    def use_offset_code(self):
        self.used_times += 1
        self.save()
