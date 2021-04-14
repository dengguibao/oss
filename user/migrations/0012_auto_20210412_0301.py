# Generated by Django 3.1.7 on 2021-04-12 03:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0011_auto_20210412_0246'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='level',
            field=models.IntegerField(default=0, max_length=1, verbose_name='user level, max allow 3 leve'),
        ),
        migrations.AddField(
            model_name='profile',
            name='root_uid',
            field=models.CharField(blank=True, default=None, max_length=50, null=True, verbose_name='sub usesr root username'),
        ),
    ]