# Generated by Django 3.1.7 on 2021-04-25 03:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('buckets', '0009_buckets_permission'),
    ]

    operations = [
        migrations.AddField(
            model_name='bucketregion',
            name='state',
            field=models.CharField(default='e', max_length=1, verbose_name='region state'),
        ),
    ]
