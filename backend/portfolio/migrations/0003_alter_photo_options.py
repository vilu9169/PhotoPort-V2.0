# Generated by Django 3.2.12 on 2024-12-23 23:39

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('portfolio', '0002_photo_order'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='photo',
            options={'ordering': ['order']},
        ),
    ]
