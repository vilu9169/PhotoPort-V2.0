from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("portfolio", "0008_fix_photo_derivative_columns"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="photo",
            name="portfolio_p_folder__fdfe0a_idx",
        ),
        migrations.RenameModel(
            old_name="Folder",
            new_name="Label",
        ),
        migrations.RenameField(
            model_name="photo",
            old_name="folder",
            new_name="label",
        ),
        migrations.AddIndex(
            model_name="photo",
            index=models.Index(
                fields=["label", "-order"],
                name="portfolio_p_label_i_d5274b_idx",
            ),
        ),
    ]
