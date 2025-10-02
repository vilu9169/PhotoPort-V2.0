from django.db import migrations, models
import django.db.models.deletion
import portfolio.models

class Migration(migrations.Migration):

    dependencies = [
        ("portfolio", "0006_auto_20250924_2335"),
    ]

    operations = [
        # 1) STATE-ONLY: tell Django Folder exists; do NOT create table (already exists)
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="Folder",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("title", models.CharField(max_length=120, unique=True)),
                        ("slug", models.SlugField(max_length=140, unique=True)),
                        ("description", models.TextField(blank=True)),
                        ("order", models.PositiveIntegerField(default=0)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                    ],
                    options={"ordering": ["-order", "-id"]},
                ),
            ],
            database_operations=[],
        ),

        # 2) ADD THE FK COLUMN BEFORE THE INDEX
        migrations.AddField(
            model_name="photo",
            name="folder",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="photos",
                to="portfolio.folder",
            ),
        ),

        # 3) NOW add the index that uses 'folder' and '-order'
        migrations.AddIndex(
            model_name="photo",
            index=models.Index(fields=["folder", "-order"], name="portfolio_p_folder__fdfe0a_idx"),
        ),

        # 4) other changes (order doesn’t matter vs the above two)
        migrations.AlterModelOptions(
            name="photo",
            options={"ordering": ["-order", "-id"]},
        ),
        migrations.AddField(
            model_name="photo",
            name="blur_data_url",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="photo",
            name="preview",
            field=models.ImageField(blank=True, null=True, upload_to=portfolio.models.photo_preview_upload_to),
        ),
        migrations.AddField(
            model_name="photo",
            name="thumb",
            field=models.ImageField(blank=True, null=True, upload_to=portfolio.models.photo_thumb_upload_to),
        ),
        migrations.AlterField(
            model_name="photo",
            name="image",
            field=models.ImageField(upload_to=portfolio.models.photo_upload_to),
        ),
    ]
