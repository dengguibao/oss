# Generated by Django 3.1.7 on 2021-04-06 02:29

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('objects', '0009_auto_20210402_0628'),
    ]

    operations = [
        migrations.AlterField(
            model_name='objectacl',
            name='object',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='object_acl', to='objects.objects'),
        ),
    ]