# Generated by Django 3.2.2 on 2021-05-27 07:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('buckets', '0014_auto_20210510_0301'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bucketacl',
            name='acl_bid',
            field=models.AutoField(auto_created=True, primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name='bucketregion',
            name='reg_id',
            field=models.AutoField(auto_created=True, primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name='buckettype',
            name='bucket_type_id',
            field=models.AutoField(auto_created=True, primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name='offset',
            name='off_id',
            field=models.AutoField(auto_created=True, primary_key=True, serialize=False),
        ),
    ]
