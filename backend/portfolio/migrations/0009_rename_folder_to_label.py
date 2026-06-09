from django.db import migrations, models


OLD_TABLE = "portfolio_folder"
NEW_TABLE = "portfolio_label"
PHOTO_TABLE = "portfolio_photo"
OLD_COLUMN = "folder_id"
NEW_COLUMN = "label_id"
OLD_INDEX = "portfolio_p_folder__fdfe0a_idx"
NEW_INDEX = "portfolio_p_label_i_d5274b_idx"


def _table_names(schema_editor):
    with schema_editor.connection.cursor() as cursor:
        return set(schema_editor.connection.introspection.table_names(cursor))


def _column_names(schema_editor, table_name):
    with schema_editor.connection.cursor() as cursor:
        description = schema_editor.connection.introspection.get_table_description(
            cursor,
            table_name,
        )
    return {column.name for column in description}


def reconcile_label_schema(apps, schema_editor):
    quote = schema_editor.quote_name
    tables = _table_names(schema_editor)

    if OLD_TABLE in tables and NEW_TABLE not in tables:
        schema_editor.execute(
            f"ALTER TABLE {quote(OLD_TABLE)} RENAME TO {quote(NEW_TABLE)}"
        )
        tables.remove(OLD_TABLE)
        tables.add(NEW_TABLE)

    if PHOTO_TABLE not in tables:
        return

    columns = _column_names(schema_editor, PHOTO_TABLE)
    if OLD_COLUMN in columns and NEW_COLUMN not in columns:
        schema_editor.execute(
            f"ALTER TABLE {quote(PHOTO_TABLE)} "
            f"RENAME COLUMN {quote(OLD_COLUMN)} TO {quote(NEW_COLUMN)}"
        )
        columns.remove(OLD_COLUMN)
        columns.add(NEW_COLUMN)

    schema_editor.execute(f"DROP INDEX IF EXISTS {quote(OLD_INDEX)}")
    if NEW_COLUMN in columns:
        schema_editor.execute(
            f"CREATE INDEX IF NOT EXISTS {quote(NEW_INDEX)} "
            f"ON {quote(PHOTO_TABLE)} "
            f"({quote(NEW_COLUMN)}, {quote('order')} DESC)"
        )


def restore_folder_schema(apps, schema_editor):
    quote = schema_editor.quote_name
    tables = _table_names(schema_editor)

    if PHOTO_TABLE in tables:
        columns = _column_names(schema_editor, PHOTO_TABLE)
        schema_editor.execute(f"DROP INDEX IF EXISTS {quote(NEW_INDEX)}")
        if NEW_COLUMN in columns and OLD_COLUMN not in columns:
            schema_editor.execute(
                f"ALTER TABLE {quote(PHOTO_TABLE)} "
                f"RENAME COLUMN {quote(NEW_COLUMN)} TO {quote(OLD_COLUMN)}"
            )
            columns.remove(NEW_COLUMN)
            columns.add(OLD_COLUMN)
        if OLD_COLUMN in columns:
            schema_editor.execute(
                f"CREATE INDEX IF NOT EXISTS {quote(OLD_INDEX)} "
                f"ON {quote(PHOTO_TABLE)} "
                f"({quote(OLD_COLUMN)}, {quote('order')} DESC)"
            )

    if NEW_TABLE in tables and OLD_TABLE not in tables:
        schema_editor.execute(
            f"ALTER TABLE {quote(NEW_TABLE)} RENAME TO {quote(OLD_TABLE)}"
        )


class Migration(migrations.Migration):
    dependencies = [
        ("portfolio", "0008_fix_photo_derivative_columns"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    reconcile_label_schema,
                    reverse_code=restore_folder_schema,
                ),
            ],
            state_operations=[
                migrations.RemoveIndex(
                    model_name="photo",
                    name=OLD_INDEX,
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
                        name=NEW_INDEX,
                    ),
                ),
            ],
        ),
    ]
