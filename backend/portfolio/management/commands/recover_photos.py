# backend/portfolio/management/commands/recover_photos.py
"""
Recover Photo records from image files on disk.
This will recreate Photo objects for images that exist but aren't in the database.
Note: Metadata (titles, descriptions, labels) will be lost and set to defaults.
"""
from django.core.management.base import BaseCommand
from django.core.files import File
from django.db import transaction
from portfolio.models import Photo
from pathlib import Path
import os


class Command(BaseCommand):
    help = "Recover Photo records from image files on disk (metadata will be lost)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be recovered without actually creating records.",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        from django.conf import settings
        base_dir = Path(settings.BASE_DIR)
        media_dir = base_dir / "media" / "photos"

        if not media_dir.exists():
            self.stdout.write(self.style.ERROR(f"Media directory not found: {media_dir}"))
            return

        # Find all image files
        image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
        image_files = []
        
        # Recursively find all image files
        for ext in image_extensions:
            image_files.extend(media_dir.rglob(f"*{ext}"))
            image_files.extend(media_dir.rglob(f"*{ext.upper()}"))

        # Filter out thumbnails and previews
        image_files = [
            f for f in image_files
            if "thumbs" not in str(f) and "previews" not in str(f)
        ]

        if not image_files:
            self.stdout.write(self.style.WARNING("No image files found"))
            return

        # Get existing photo paths from database
        existing_paths = set(
            Photo.objects.values_list("image", flat=True)
        )

        recovered_count = 0
        skipped_count = 0

        for img_path in sorted(image_files):
            # Get relative path from media directory
            try:
                relative_path = img_path.relative_to(base_dir / "media")
                db_path = str(relative_path).replace("\\", "/")
            except ValueError:
                # File is not under media directory
                continue

            # Skip if already in database
            if db_path in existing_paths:
                skipped_count += 1
                continue

            # Generate title from filename
            title = img_path.stem.replace("-", " ").replace("_", " ")
            title = " ".join(word.capitalize() for word in title.split())

            if opts["dry_run"]:
                self.stdout.write(f"Would recover: {title} ({img_path.name})")
                recovered_count += 1
            else:
                # Create Photo object
                photo = Photo(
                    title=title,
                    description=f"Recovered image: {img_path.name}",
                    category="",  # Empty category
                )

                # Assign the existing file
                with img_path.open("rb") as f:
                    photo.image.save(
                        img_path.name,
                        File(f),
                        save=False,
                    )

                # Save to trigger derivative generation
                photo.save()

                recovered_count += 1
                self.stdout.write(f"✓ Recovered: {title} ({img_path.name})")

        if opts["dry_run"]:
            self.stdout.write(
                self.style.WARNING(
                    f"\nDRY RUN: Would recover {recovered_count} photos. "
                    f"Skipped {skipped_count} existing."
                )
            )
            self.stdout.write("Run without --dry-run to actually recover them.")
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nRecovered {recovered_count} photos. "
                    f"Skipped {skipped_count} existing."
                )
            )
            self.stdout.write(f"Total photos in database: {Photo.objects.count()}")
