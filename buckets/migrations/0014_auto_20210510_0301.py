# Generated by Django 3.2.2 on 2021-05-10 03:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('buckets', '0013_auto_20210429_0623'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='buckets',
            name='capacity',
        ),
        migrations.RemoveField(
            model_name='buckets',
            name='duration',
        ),
        migrations.RemoveField(
            model_name='buckets',
            name='start_time',
        ),
        migrations.AddField(
            model_name='buckets',
            name='backup',
            field=models.BooleanField(default=False, verbose_name='backup flag'),
        ),
        migrations.AddField(
            model_name='buckets',
            name='pid',
            field=models.IntegerField(default=0, verbose_name='parent id of bucket'),
        ),
        migrations.AddField(
            model_name='buckets',
            name='read_only',
            field=models.BooleanField(default=False, verbose_name='read only flag'),
        ),
    ]