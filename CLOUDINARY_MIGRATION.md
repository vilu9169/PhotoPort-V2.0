# S3 to Cloudinary migration

The Django backend owns all Cloudinary credentials and uploads. The frontend
only needs `NEXT_PUBLIC_API_URL`; never put `CLOUDINARY_API_SECRET` in a
frontend environment file or GitHub Pages setting.

## 1. Configure the backend locally

Move the Cloudinary credentials from `frontend/.env` to
`backend/backend/.env`. Prefer the single value shown in the Cloudinary
dashboard:

```dotenv
CLOUDINARY_URL=cloudinary://api_key:api_secret@cloud_name
```

Alternatively, set all three variables:

```dotenv
CLOUDINARY_CLOUD_NAME=...
CLOUDINARY_API_KEY=...
CLOUDINARY_API_SECRET=...
```

Remove the old `AWS_*` variables while migrating so Django cannot fall back to
S3. Keep `DATABASE_URL` set because the database contains the filenames and
portfolio metadata that connect each row to its image.

## 2. Preview the migration

From the `backend` directory, run:

```bash
python manage.py check
python manage.py sync_media_to_storage \
  --source-media-root /home/viktor/photos \
  --dry-run
```

Review the missing-file count before continuing. The command supports both
`/home/viktor/photos/japan/...` and a media root containing
`photos/japan/...`.

## 3. Upload to Cloudinary

Use the same database that production uses, then run:

```bash
python manage.py sync_media_to_storage \
  --source-media-root /home/viktor/photos
```

The command preserves the names stored in the database. It uploads originals,
thumbnails, and previews, skips assets already present in Cloudinary, and can
be rerun safely.

## 4. Configure Render

Add `CLOUDINARY_URL` (or the three separate Cloudinary variables) to the
backend service environment. Remove `AWS_STORAGE_BUCKET_NAME`,
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and other `AWS_S3_*` variables.
Redeploy the backend.

No frontend code change is required. The API serializer returns absolute
Cloudinary URLs and the gallery already accepts absolute URLs.

## 5. Verify before deleting S3

1. Open the production `/api/photos/` endpoint and confirm its image URLs use
   `res.cloudinary.com`.
2. Load the gallery and open several detail views.
3. Upload one new photo through the Django staff page.
4. Delete that test photo and confirm it is removed from Cloudinary.
5. Keep the local backup until all checks pass. Only then remove the S3 bucket.
