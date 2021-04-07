# Generated by Django 3.1.7 on 2021-04-02 06:28

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('buckets', '0008_auto_20210401_0849'),
        ('objects', '0008_auto_20210401_0854'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='objects',
            unique_together={('bucket', 'owner', 'key', 'version_id')},
        ),
    ]