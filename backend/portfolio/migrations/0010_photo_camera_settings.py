from django.db import migrations, models


PHOTO_TABLE = "portfolio_photo"
CAMERA_FIELDS = (
    ("aperture", 20),
    ("iso", 20),
    ("shutter_speed", 30),
)


def _column_names(schema_editor):
    with schema_editor.connection.cursor() as cursor:
        description = schema_editor.connection.introspection.get_table_description(
            cursor,
            PHOTO_TABLE,
        )
    return {column.name for column in description}


def _camera_field(photo_model, name, max_length):
    for field in photo_model._meta.local_fields:
        if field.name == name:
            return field

    field = models.CharField(blank=True, default="", max_length=max_length)
    field.contribute_to_class(photo_model, name)
    return field


def ensure_camera_columns(apps, schema_editor):
    tables = set(schema_editor.connection.introspection.table_names())
    if PHOTO_TABLE not in tables:
        return

    photo_model = apps.get_model("portfolio", "Photo")
    columns = _column_names(schema_editor)

    # SQLite rebuilds tables for these additions. Register physical columns on
    # the historical model first so a partial schema is preserved in a rebuild.
    for name, max_length in CAMERA_FIELDS:
        if name in columns:
            _camera_field(photo_model, name, max_length)

    for name, max_length in CAMERA_FIELDS:
        if name in columns:
            continue
        field = _camera_field(photo_model, name, max_length)
        schema_editor.add_field(
            photo_model,
            field,
        )
        columns.add(name)


class Migration(migrations.Migration):
    dependencies = [
        ("portfolio", "0009_rename_folder_to_label"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    ensure_camera_columns,
                    reverse_code=migrations.RunPython.noop,
                ),
            ],
            state_operations=[
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
            ],
        ),
    ]
