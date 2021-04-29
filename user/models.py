from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.authtoken.models import Token
from account.models import Plan
from django.conf import settings
from common.func import build_ceph_userinfo, random_build_str
import time


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=11, blank=False, unique=True)
    phone_verify = models.BooleanField(blank=False, default=False)
    parent_uid = models.CharField(max_length=50, verbose_name='sub user parent username', blank=True)
    root_uid = models.CharField(max_length=50, verbose_name='sub user root username',
                                null=True, blank=True, default=None)
    level = models.IntegerField(verbose_name='sub user deep level, max allow 3 leve',
                                default=0, blank=False, null=False)
    balance = models.FloatField(verbose_name='user account balance', default=0.0)
    offset = models.FloatField(verbose_name='user offset', default=1.0)
    is_subuser = models.BooleanField(verbose_name='is sub user', default=False, blank=False)

    def recharge(self, value: float):
        self.balance += value
        self.save()
        return True

    def cost(self, value: float):
        x = self.balance - value
        if x < 0:
            return False
        else:
            self.balance = x
            self.save()
            return True

    def __str__(self):
        return f'user profile: {self.user.username}, {self.user.first_name}'


class Keys(models.Model):
    key_id = models.AutoField(primary_key=True, auto_created=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='keys')
    ceph_uid = models.CharField(max_length=20, blank=True, verbose_name='ceph uid')
    ceph_secret_key = models.CharField(max_length=50, blank=True, null=True, unique=True,)
    ceph_access_key = models.CharField(max_length=50, blank=True, null=True, unique=True,)
    key_type = models.CharField(max_length=5, blank=True, default='s3')
    user_secret_key = models.CharField(max_length=50, blank=True, null=True, unique=True,)
    user_access_key = models.CharField(max_length=50, blank=True, null=True, unique=True,)

    def __str__(self):
        return f'username: {self.user.username}, user_access_key: {self.user_access_key}, user_secret_key: {self.user_secret_key}'

    def init(self):
        uid, access_key, secret_key = build_ceph_userinfo()
        self.ceph_uid = uid
        self.ceph_access_key = access_key
        self.ceph_secret_key = secret_key
        self.user_access_key = random_build_str(32)
        self.user_secret_key = random_build_str(40)
        self.save()

    def change_user_key(self):
        self.user_access_key = random_build_str(32)
        self.user_secret_key = random_build_str(40)
        self.save()


class CapacityQuota(models.Model):
    c_id = models.AutoField(primary_key=True, auto_created=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='capacity_quota')
    start_time = models.IntegerField(verbose_name="start time", default=int(time.time()), blank=False)
    capacity = models.IntegerField(verbose_name="capacity", default=0, blank=False)
    duration = models.IntegerField(verbose_name="duration", default=0, blank=False)
    # 后端服务器已同步标志，如果已经同步，则该标志为0, 1表示为ceph后端还未同步
    sync = models.IntegerField(default=0, blank=False)
    create_time = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_capacity_quota'

    def __str__(self):
        return f'{self.user.username}, {self.capacity}'

    def valid(self):
        if time.time() > self.start_time + (self.duration * 86400):
            return False

        if self.capacity <= 0:
            return False

        return True

    def renewal(self, days: int, cap: int):
        start_time = self.start_time if self.start_time else time.time()
        new_start = start_time + (86400 * self.duration)
        self.duration = days
        self.capacity = cap
        self.start_time = new_start
        self.sync = 0
        self.save()
        return self.json

    def ceph_sync(self):
        self.sync = 0
        self.save()

    @property
    def json(self):
        return {
            'start_time': time.strftime('%F', time.localtime(self.start_time)),
            'duration': self.duration,
            'capacity': self.capacity,
        }


class BandwidthQuota(models.Model):
    b_id = models.AutoField(primary_key=True, auto_created=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='bandwidth_quota')
    start_time = models.IntegerField(verbose_name="start time", default=int(time.time()), blank=False)
    bandwidth = models.IntegerField(verbose_name="bandwidth", default=settings.USER_MIN_BANDWIDTH, blank=False)
    duration = models.IntegerField(verbose_name="duration", default=0, blank=False)
    create_time = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_bandwidth_quota'

    def __str__(self):
        return f'{self.user.username}, {self.bandwidth}'

    def user_bandwidth(self):
        if time.time() > self.start_time + (self.duration * 86400):
            return settings.USER_MIN_BANDWIDTH

        return self.bandwidth

    def renewal(self, days: int, bandwidth: int):
        start_time = self.start_time if self.start_time else time.time()
        new_start = start_time + (86400 * self.duration)
        self.duration = days
        self.bandwidth = bandwidth
        self.start_time = new_start
        self.save()
        return self.json

    @property
    def json(self):
        return {
            'start_time': time.strftime('%F', time.localtime(self.start_time)),
            'duration': self.duration,
            'capacity': self.bandwidth,
        }


@receiver(post_save, sender=User)
def handle_create_user(sender, instance, created, **kwargs):
    if created:
        CapacityQuota.objects.create(user=instance)
        BandwidthQuota.objects.create(user=instance)
        Keys.objects.create(user=instance)
        Profile.objects.create(user=instance)
        Token.objects.create(user=instance)

