from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=11, blank=False)
    phone_verify = models.BooleanField(blank=False, default=False)
    secret_key = models.CharField(max_length=32, blank=True, verbose_name='ceph access key')
    access_key = models.CharField(max_length=32, blank=True, verbose_name='ceph access secret')
    key_type = models.CharField(max_length=5, blank=True)
    parent_uid = models.CharField(max_length=50, verbose_name='parent account username', blank=True)
    is_subuser = models.BooleanField(verbose_name='is sub user', default=False, blank=False)


# @receiver(post_save, sender=User)
# def handle_create_user(sender, instance, created, **kwargs):
#     print(**kwargs)
#     if created:
#         Profile.objects.create(user=instance, **kwargs)
#     else:
#         print(**kwargs)
#         Profile.objects.filter(user=instance).update(**kwargs)


class Money(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.FloatField(verbose_name="account balance", default=0, blank=False)

    def charge(self, value: float):
        self.amount += value
        self.save()

    def cost(self, value: float):
        self.amount -= value
        self.save()
