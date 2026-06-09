from django.db import migrations


def ensure_postgres_derivative_columns(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    schema_editor.execute(
        """
        ALTER TABLE portfolio_photo
        ADD COLUMN IF NOT EXISTS thumb varchar(100);

        ALTER TABLE portfolio_photo
        ADD COLUMN IF NOT EXISTS preview varchar(100);

        ALTER TABLE portfolio_photo
        ADD COLUMN IF NOT EXISTS blur_data_url text NOT NULL DEFAULT '';
        """
    )


class Migration(migrations.Migration):

    dependencies = [
        ("portfolio", "0007_auto_20251002_0047"),
    ]

    operations = [
        migrations.RunPython(
            ensure_postgres_derivative_columns,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
