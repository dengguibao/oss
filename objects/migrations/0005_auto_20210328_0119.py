# Generated by Django 3.1.7 on 2021-03-28 01:19

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('buckets', '0004_remove_buckets_bucket_type'),
        ('objects', '0004_objects_key'),
    ]

    operations = [
        migrations.AlterField(
            model_name='objects',
            name='bucket',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='object_bucket', to='buckets.buckets'),
        ),
        migrations.AlterField(
            model_name='objects',
            name='owner',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='object_owner', to=settings.AUTH_USER_MODEL),
        ),
    ]