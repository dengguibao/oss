from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.authtoken.models import Token
import time


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=11, blank=False, unique=True)
    phone_verify = models.BooleanField(blank=False, default=False)
    ceph_uid = models.CharField(max_length=20, blank=True, verbose_name='ceph uid')
    secret_key = models.CharField(max_length=50, blank=True, default=None,
                                  null=True, unique=True, verbose_name='ceph access key')
    access_key = models.CharField(max_length=50, blank=True, default=None,
                                  null=True, unique=True, verbose_name='ceph access secret')
    key_type = models.CharField(max_length=5, blank=True)
    parent_uid = models.CharField(max_length=50, verbose_name='sub account parent account username', blank=True)
    root_uid = models.CharField(max_length=50, verbose_name='sub usesr root username',
                                null=True, blank=True, default=None)
    level = models.IntegerField(verbose_name='user level, max allow 3 leve',
                                default=0, blank=False, null=False)
    bandwidth = models.IntegerField(verbose_name='user download bandwidth', default=4, blank=False)
    is_subuser = models.BooleanField(verbose_name='is sub user', default=False, blank=False)

    def __str__(self):
        return f'user profile: {self.user.username}, {self.user.first_name}'


class Quota(models.Model):
    c_id = models.AutoField(primary_key=True, auto_created=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='quota')
    start_time = models.IntegerField(verbose_name="start time", default=0, blank=False)
    capacity = models.IntegerField(verbose_name="capacity", default=0, blank=False)
    duration = models.IntegerField(verbose_name="duration", default=0, blank=False)
    create_time = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user.username}, {self.capacity}'

    def calculate_valid_date(self):
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
        self.save()


class Money(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='money')
    amount = models.FloatField(verbose_name="account balance", default=0, blank=False)

    def charge(self, value: float):
        self.amount += value
        self.save()

    def cost(self, value: float):
        x = self.amount - value
        if x <= 0:
            x = 0
        self.amount = x
        self.save()


@receiver(post_save, sender=User)
def handle_create_user(sender, instance, created, **kwargs):
    if created:
        Quota.objects.create(user=instance)
        Money.objects.create(user=instance)
        Profile.objects.create(user=instance)
        Token.objects.create(user=instance)
