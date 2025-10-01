# photos/management/commands/backfill_derivatives.py
from django.core.management.base import BaseCommand
from portfolio.models import Photo

class Command(BaseCommand):
    help = "Generate thumbnail/preview/blur_data_url for existing photos"

    def handle(self, *args, **opts):
        qs = Photo.objects.all().order_by("id")
        total = qs.count()
        for i, p in enumerate(qs, 1):
            p.generate_derivatives(force=True)
            p.save(update_fields=["thumb", "preview", "blur_data_url"])
            self.stdout.write(self.style.SUCCESS(f"[{i}/{total}] Processed Photo #{p.id}"))
