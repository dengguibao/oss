from django.db import models
from django.contrib.auth.models import User
from buckets.models import Buckets


# Create your models here.
class Objects(models.Model):
    FILE_TYPE = (
        ('f', 'file'),
        ('d', 'directory')
    )
    obj_id = models.IntegerField(primary_key=True, auto_created=True)
    bucket = models.ForeignKey(Buckets, on_delete=models.CASCADE, null=False, blank=False, related_name='object_bucket')
    name = models.CharField(verbose_name="filename", max_length=63, blank=False)
    type = models.CharField(verbose_name="file type", max_length=1, choices=FILE_TYPE, blank=False)
    root = models.CharField(verbose_name="root path", max_length=300, blank=True, null=True)
    file_size = models.IntegerField(verbose_name="file size", blank=True, default=0)
    md5 = models.CharField(verbose_name='upload file md5', max_length=50, blank=True, null=True)
    etag = models.CharField(verbose_name='s3 etag', max_length=50, blank=True, null=True)
    key = models.CharField(verbose_name='keys', max_length=300, blank=True, null=True)
    version_id = models.CharField(verbose_name='version id', max_length=50, blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True, related_name="object_owner")
    upload_time = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (
            'bucket', 'name',  'owner', 'type', 'root'
        )