# Generated by Django 3.2.2 on 2021-08-25 02:05

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('buckets', '0001_initial'),
        ('objects', '0001_initial'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='objects',
            unique_together={('bucket', 'key')},
        ),
    ]
