from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("portfolio", "0009_rename_folder_to_label"),
    ]

    operations = [
        migrations.AddField(
            model_name="photo",
            name="aperture",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AddField(
            model_name="photo",
            name="iso",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AddField(
            model_name="photo",
            name="shutter_speed",
            field=models.CharField(blank=True, default="", max_length=30),
        ),
    ]
