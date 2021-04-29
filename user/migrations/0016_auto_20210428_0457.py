# Generated by Django 3.1.7 on 2021-04-28 04:57

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('user', '0015_auto_20210427_0455'),
    ]

    operations = [
        migrations.CreateModel(
            name='BandwidthQuota',
            fields=[
                ('b_id', models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ('start_time', models.IntegerField(default=1619585879, verbose_name='start time')),
                ('bandwidth', models.IntegerField(default=4, verbose_name='bandwidth')),
                ('duration', models.IntegerField(default=0, verbose_name='duration')),
                ('create_time', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='bandwidth_quota', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'user_bandwidth_quota',
            },
        ),
        migrations.CreateModel(
            name='CapacityQuota',
            fields=[
                ('c_id', models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ('start_time', models.IntegerField(default=1619585879, verbose_name='start time')),
                ('capacity', models.IntegerField(default=0, verbose_name='capacity')),
                ('duration', models.IntegerField(default=0, verbose_name='duration')),
                ('create_time', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='capacity_quota', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'user_capacity_quota',
            },
        ),
        migrations.CreateModel(
            name='Keys',
            fields=[
                ('key_id', models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ('ceph_uid', models.CharField(blank=True, max_length=20, verbose_name='ceph uid')),
                ('ceph_secret_key', models.CharField(blank=True, max_length=50, null=True, unique=True)),
                ('ceph_access_key', models.CharField(blank=True, max_length=50, null=True, unique=True)),
                ('key_type', models.CharField(blank=True, default='s3', max_length=5)),
                ('user_secret_key', models.CharField(blank=True, max_length=50, null=True, unique=True)),
                ('user_access_key', models.CharField(blank=True, max_length=50, null=True, unique=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='keys', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.RemoveField(
            model_name='profile',
            name='access_key',
        ),
        migrations.RemoveField(
            model_name='profile',
            name='bandwidth',
        ),
        migrations.RemoveField(
            model_name='profile',
            name='ceph_uid',
        ),
        migrations.RemoveField(
            model_name='profile',
            name='key_type',
        ),
        migrations.RemoveField(
            model_name='profile',
            name='secret_key',
        ),
        migrations.AddField(
            model_name='profile',
            name='offset',
            field=models.FloatField(default=1.0, verbose_name='user offset'),
        ),
        migrations.AlterField(
            model_name='profile',
            name='level',
            field=models.IntegerField(default=0, verbose_name='sub user deep level, max allow 3 leve'),
        ),
        migrations.AlterField(
            model_name='profile',
            name='parent_uid',
            field=models.CharField(blank=True, max_length=50, verbose_name='sub user parent username'),
        ),
        migrations.AlterField(
            model_name='profile',
            name='root_uid',
            field=models.CharField(blank=True, default=None, max_length=50, null=True, verbose_name='sub user root username'),
        ),
        migrations.DeleteModel(
            name='Quota',
        ),
    ]
