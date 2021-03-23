# Generated by Django 3.1.7 on 2021-03-22 06:22

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
            name='Profile',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone', models.CharField(max_length=11)),
                ('phone_verify', models.IntegerField(default=0)),
                ('access_key', models.CharField(blank=True, max_length=32, verbose_name='ceph access key')),
                ('access_secret', models.CharField(blank=True, max_length=32, verbose_name='ceph access secret')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
