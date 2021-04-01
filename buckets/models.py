from django.db import models
from django.contrib.auth.models import User
import time


class BucketRegion(models.Model):
    reg_id = models.IntegerField(primary_key=True, auto_created=True)
    name = models.CharField(max_length=100, verbose_name='name', blank=False, null=False)
    secret_key = models.CharField(verbose_name='secret key', max_length=50)
    access_key = models.CharField(verbose_name='access key', max_length=50)
    server = models.CharField(verbose_name='server ip', max_length=20)
    create_time = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name, self.server


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
    bucket_id = models.AutoField(primary_key=True, auto_created=True)
    name = models.CharField(verbose_name='bucket name', unique=True, max_length=63, blank=False, null=True)
    capacity = models.IntegerField(verbose_name="capacity", default=0, blank=False)
    duration = models.IntegerField(verbose_name="duration", default=0, blank=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user', null=True, blank=True)
    start_time = models.IntegerField(verbose_name='start time', blank=False, default=0)
    version_control = models.BooleanField(verbose_name="version control", default=False, blank=False)
    # bucket_type = models.ForeignKey(BucketType, on_delete=models.SET_NULL, null=True, blank=True)
    bucket_region = models.ForeignKey(BucketRegion, on_delete=models.SET_NULL, null=True, blank=True)
    state = models.CharField(choices=STATE, verbose_name='state', max_length=1, blank=False)
    create_time = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.bucket_id}, {self.name}'

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
    acl_bid = models.IntegerField(primary_key=True, auto_created=True)
    permission = models.CharField(verbose_name="bucket permission", max_length=50, blank=False, default='private')
    bucket = models.ForeignKey(Buckets, on_delete=models.CASCADE, related_name='bucket_acl')
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    create_time = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.bucket.name}, {self.permission}'


class Offset(models.Model):
    off_id = models.IntegerField(primary_key=True, auto_created=True)
    code = models.CharField(verbose_name='offset code', unique=True, max_length=6, blank=False)
    offset = models.FloatField(verbose_name='offset value', blank=False)
    used_times = models.IntegerField(verbose_name='used times', blank=False, default=0)
    max_use_times = models.IntegerField(verbose_name='max use times', blank=False, default=0)
    valid_days = models.IntegerField(verbose_name='valid days', blank=False, default=0)
    create_time = models.DateTimeField(auto_now=True)

    def __str__(self):
        return '%s' % self.code

    def get_offset_value(self):
        if self.used_times < self.max_use_times or \
                self.create_time.timestamp()+(86400*self.valid_days) < time.time():
            return self.offset
        else:
            return 1

    def use_offset_code(self):
        self.used_times += 1
        self.save()
