# Generated by Django 3.2.12 on 2024-12-23 23:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portfolio', '0004_alter_photo_order'),
    ]

    operations = [
        migrations.AlterField(
            model_name='photo',
            name='order',
            field=models.IntegerField(default=0),
        ),
    ]
