from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

from portfolio.models import Photo


class Command(BaseCommand):
    help = (
        "Upload existing media files from local disk to the currently configured "
        "Django default storage backend."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--source-media-root",
            default=str(Path(settings.BASE_DIR) / "media"),
            help="Local source media directory that contains image paths from DB.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be uploaded without writing to storage.",
        )

    def handle(self, *args, **options):
        source_media_root = Path(options["source_media_root"]).expanduser().resolve()
        dry_run = options["dry_run"]

        if not source_media_root.exists():
            self.stdout.write(
                self.style.ERROR(f"Source media root does not exist: {source_media_root}")
            )
            return

        uploaded = 0
        skipped_missing_local = 0
        skipped_already_remote = 0
        updated_records = 0

        fields = ("image", "thumb", "preview")

        for photo in Photo.objects.all().order_by("id"):
            changed = False

            for field_name in fields:
                field_file = getattr(photo, field_name, None)
                storage_name = getattr(field_file, "name", "") or ""
                if not storage_name:
                    continue

                local_path = self._find_local_file(source_media_root, storage_name)
                if local_path is None:
                    skipped_missing_local += 1
                    self.stdout.write(
                        self.style.WARNING(f"Missing local file: {storage_name}")
                    )
                    continue

                if dry_run:
                    self.stdout.write(f"Would upload {field_name}: {storage_name}")
                    uploaded += 1
                    continue

                if default_storage.exists(storage_name):
                    skipped_already_remote += 1
                    continue

                with local_path.open("rb") as file_obj:
                    saved_name = default_storage.save(storage_name, File(file_obj))

                uploaded += 1

                if saved_name != storage_name:
                    setattr(photo, field_name, saved_name)
                    changed = True

            if changed and not dry_run:
                updates = {
                    field_name: getattr(photo, field_name).name
                    for field_name in fields
                }
                Photo.objects.filter(pk=photo.pk).update(**updates)
                updated_records += 1

        self.stdout.write(self.style.SUCCESS(f"Uploaded files: {uploaded}"))
        self.stdout.write(f"Skipped (missing locally): {skipped_missing_local}")
        self.stdout.write(f"Skipped (already in storage): {skipped_already_remote}")
        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f"Updated DB rows: {updated_records}"))

    @staticmethod
    def _find_local_file(source_media_root, storage_name):
        storage_path = Path(storage_name)
        candidates = [source_media_root / storage_path]

        # An S3 download of the "photos/" prefix often produces a local
        # /path/to/photos directory whose contents begin below that prefix.
        if storage_path.parts and storage_path.parts[0] == source_media_root.name:
            candidates.append(source_media_root.joinpath(*storage_path.parts[1:]))

        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return None
