# Generated by Django 3.1.7 on 2021-03-26 04:21

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('buckets', '0003_auto_20210325_0926'),
    ]

    operations = [
        migrations.CreateModel(
            name='Objects',
            fields=[
                ('upload_time', models.DateTimeField(auto_created=True)),
                ('obj_id', models.IntegerField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=63, verbose_name='filename')),
                ('type', models.CharField(choices=[('f', 'file'), ('d', 'directory')], max_length=1, verbose_name='file type')),
                ('root', models.CharField(max_length=300, verbose_name='root path')),
                ('file_size', models.IntegerField(blank=True, default=0, verbose_name='file size')),
                ('md5', models.CharField(blank=True, max_length=50, null=True, verbose_name='upload file md5')),
                ('etag', models.CharField(blank=True, max_length=50, null=True, verbose_name='s3 etag')),
                ('bucket', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='buckets.buckets')),
                ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='objects', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('bucket', 'name', 'owner', 'type', 'root')},
            },
        ),
    ]
