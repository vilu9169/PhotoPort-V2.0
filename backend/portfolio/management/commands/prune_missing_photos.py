from django.core.management.base import BaseCommand
from django.core.files.storage import default_storage
from portfolio.models import Photo

class Command(BaseCommand):
    help = "Delete Photo rows whose file is missing from storage"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Only report")

    def handle(self, dry_run, **kwargs):
        missing_ids = []
        for p in Photo.objects.iterator():
            name = getattr(p.image, "name", "") or ""
            if not name or not default_storage.exists(name):
                missing_ids.append(p.id)

        self.stdout.write(f"Missing files: {len(missing_ids)}")
        if dry_run or not missing_ids:
            self.stdout.write("Dry run or nothing to delete.")
            return

        deleted, _ = Photo.objects.filter(id__in=missing_ids).delete()
        self.stdout.write(f"Deleted {deleted} objects.")
