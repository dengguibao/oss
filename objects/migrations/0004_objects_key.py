# Generated by Django 3.1.7 on 2021-03-26 06:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('objects', '0003_objects_version_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='objects',
            name='key',
            field=models.CharField(blank=True, max_length=300, null=True, verbose_name='keys'),
        ),
    ]
