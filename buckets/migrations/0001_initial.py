# Generated by Django 3.1.7 on 2021-03-24 02:33

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BucketType',
            fields=[
                ('bucket_type_id', models.IntegerField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=20, verbose_name='bucket type name')),
                ('price', models.FloatField(verbose_name='bucket price')),
                ('create_time', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='Offset',
            fields=[
                ('off_id', models.IntegerField(auto_created=True, primary_key=True, serialize=False)),
                ('code', models.CharField(max_length=6, verbose_name='offset code')),
                ('offset', models.FloatField(verbose_name='offset value')),
                ('used_times', models.IntegerField(default=0, verbose_name='used times')),
                ('max_use_times', models.IntegerField(default=0, verbose_name='max use times')),
                ('valid_days', models.IntegerField(default=0, verbose_name='valid days')),
                ('create_time', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='Buckets',
            fields=[
                ('bucket_id', models.IntegerField(auto_created=True, primary_key=True, serialize=False)),
                ('start_time', models.IntegerField(verbose_name='start time')),
                ('state', models.CharField(max_length=1, verbose_name='state')),
                ('create_time', models.DateTimeField(auto_now=True)),
                ('bucket_type', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='buckets.buckettype')),
            ],
        ),
        migrations.CreateModel(
            name='BucketAcl',
            fields=[
                ('acl_id', models.IntegerField(auto_created=True, primary_key=True, serialize=False)),
                ('read', models.BooleanField(verbose_name='readable')),
                ('write', models.BooleanField(verbose_name='writeable')),
                ('list', models.BooleanField(verbose_name='list able')),
                ('bucket', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='buckets.buckets')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
