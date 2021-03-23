from django.db import models
from django.contrib.auth.models import User


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=11, blank=False)
    phone_verify = models.IntegerField(blank=False, default=0)
    access_key = models.CharField(max_length=32, blank=True, verbose_name='ceph access key')
    access_secret = models.CharField(max_length=32, blank=True, verbose_name='ceph access secret')
