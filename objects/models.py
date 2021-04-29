from django.db import models
from django.contrib.auth.models import User
from buckets.models import Buckets


class Objects(models.Model):
    FILE_TYPE = (
        ('f', 'file'),
        ('d', 'directory')
    )
    obj_id = models.AutoField(primary_key=True, auto_created=True)
    bucket = models.ForeignKey(Buckets, on_delete=models.CASCADE, null=False, blank=False, related_name='object_bucket')
    name = models.CharField(verbose_name="filename", max_length=1024, blank=False)
    type = models.CharField(verbose_name="file type", max_length=1, choices=FILE_TYPE, blank=False)
    root = models.CharField(verbose_name="root path", max_length=2048, blank=True, null=True)
    file_size = models.IntegerField(verbose_name="file size", blank=True, default=0)
    md5 = models.CharField(verbose_name='upload file md5', max_length=50, blank=True, null=True)
    etag = models.CharField(verbose_name='s3 etag', max_length=50, blank=True, null=True)
    key = models.CharField(verbose_name='keys', max_length=4096, blank=True, null=True)
    version_id = models.CharField(verbose_name='version id', max_length=50, blank=True, null=True)
    permission = models.CharField(max_length=50, blank=False, default='private')
    owner = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True, related_name="object_owner")
    upload_time = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'obj_id:{self.obj_id}, name:{self.name}, key:{self.key}'

    class Meta:
        unique_together = (
            'bucket', 'owner', 'key', 'version_id'
        )


class ObjectAcl(models.Model):
    acl_oid = models.IntegerField(auto_created=True, primary_key=True)
    permission = models.CharField(verbose_name="acl name", max_length=50, blank=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    object = models.ForeignKey(Objects, on_delete=models.CASCADE, related_name='object_acl')

    def __str__(self):
        return f'{self.object.name}, {self.permission}'

    @property
    def json(self):
        return {
            'acl_oid': self.acl_oid,
            'permission': self.permission,
            'user_id': self.user,
            'object_id': self.object
        }
