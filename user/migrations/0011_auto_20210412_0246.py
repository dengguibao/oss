# Generated by Django 3.1.7 on 2021-04-12 02:46

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('user', '0010_auto_20210412_0128'),
    ]

    operations = [
        migrations.CreateModel(
            name='Quota',
            fields=[
                ('c_id', models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ('start_time', models.IntegerField(default=0, verbose_name='start time')),
                ('capacity', models.IntegerField(default=0, verbose_name='capacity')),
                ('duration', models.IntegerField(default=0, verbose_name='duration')),
                ('create_time', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='quota', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.DeleteModel(
            name='Capacity',
        ),
    ]
