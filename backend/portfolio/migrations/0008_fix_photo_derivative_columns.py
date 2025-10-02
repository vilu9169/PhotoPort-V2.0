from django.db import migrations

class Migration(migrations.Migration):

    # depends on your last applied migration on Render; 0006 is safe if 0007 was faked
    dependencies = [
        ("portfolio", "0007_auto_20251002_0047"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE portfolio_photo
                ADD COLUMN IF NOT EXISTS thumb varchar(100);

                ALTER TABLE portfolio_photo
                ADD COLUMN IF NOT EXISTS preview varchar(100);

                ALTER TABLE portfolio_photo
                ADD COLUMN IF NOT EXISTS blur_data_url text NOT NULL DEFAULT '';
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
