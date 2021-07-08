from django.db import models
from django.contrib.auth.models import User
import random
import time


class BucketRegion(models.Model):
    STATE = (
        ('e', 'enable'),
        ('d', 'disable'),
    )
    reg_id = models.AutoField(primary_key=True, auto_created=True)
    name = models.CharField(max_length=100, verbose_name='name', blank=False, null=False)
    secret_key = models.CharField(verbose_name='secret key', max_length=50)
    access_key = models.CharField(verbose_name='access key', max_length=50)
    server = models.CharField(verbose_name='server ip', max_length=20)
    state = models.CharField(verbose_name='region state', max_length=1, default='e', choices=STATE)
    create_time = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name, self.server

    @property
    def json(self):
        return {
            "reg_id": self.reg_id,
            'name': self.name,
            'secret_key': self.secret_key,
            'access_key': self.access_key,
            'server': self.server,
            'state': 'enable' if self.state == 'e' else 'disabled'
        }


class BucketType(models.Model):
    bucket_type_id = models.AutoField(primary_key=True, auto_created=True)
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
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user', null=True, blank=True)
    version_control = models.BooleanField(verbose_name="version control", default=False, blank=False)
    permission = models.CharField(max_length=50, blank=False, default='private')
    bucket_region = models.ForeignKey(BucketRegion, on_delete=models.CASCADE, null=True, blank=True)
    state = models.CharField(choices=STATE, verbose_name='state', max_length=1, blank=False, default='e')
    #
    backup = models.BooleanField(verbose_name="backup flag", default=False)
    read_only = models.BooleanField(verbose_name="read only flag", default=False)
    pid = models.IntegerField(verbose_name="parent id of bucket", default=0)
    #
    create_time = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'bucket_id:{self.bucket_id}, name:{self.name}'

    def create_backup(self, region: int):
        self.backup = True
        self.save()

        Buckets.objects.create(
            name='%s-%s-backup' % (self.name, ''.join(random.sample('abcdefghijklmnopqrstuvwxyz0123456789', 8))),
            user=self.user,
            version_control=self.version_control,
            permission=self.permission,
            read_only=True,
            bucket_region_id=region,
            pid=self.bucket_id
        )


class BucketAcl(models.Model):
    acl_bid = models.AutoField(primary_key=True, auto_created=True)
    permission = models.CharField(verbose_name="bucket permission", max_length=50, blank=False, default='private')
    bucket = models.ForeignKey(Buckets, on_delete=models.CASCADE, related_name='bucket_acl')
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    create_time = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'bucket:{self.bucket.name}, permission:{self.permission}'

    @property
    def json(self):
        return {
            'acl_bid': self.acl_bid,
            'permission': self.permission,
            'bucket_id': self.bucket_id,
            'user': self.user_id,
            'create_time': self.create_time
        }


class Offset(models.Model):
    off_id = models.AutoField(primary_key=True, auto_created=True)
    code = models.CharField(verbose_name='offset code', unique=True, max_length=6, blank=False)
    offset = models.FloatField(verbose_name='offset value', blank=False)
    used_times = models.IntegerField(verbose_name='used times', blank=False, default=0)
    max_use_times = models.IntegerField(verbose_name='max use times', blank=False, default=0)
    valid_days = models.IntegerField(verbose_name='valid days', blank=False, default=0)
    create_time = models.DateTimeField(auto_now=True)

    def __str__(self):
        return 'code:%s' % self.code

    def get_offset_value(self):
        if self.used_times < self.max_use_times or \
                self.create_time.timestamp()+(86400*self.valid_days) < time.time():
            return self.offset
        else:
            return 1

    def use_offset_code(self):
        self.used_times += 1
        self.save()
