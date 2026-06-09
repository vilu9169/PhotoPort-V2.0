# Security and cost-safety runbook

Review date: June 9, 2026.

## Urgent actions

1. In Render, set a new random `SECRET_KEY` before the next deployment:

   ```bash
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```

   The application now refuses to start in production without this setting.

2. Change the Django superuser password. The repository previously tracked
   `backend/db.sqlite3`, which contains a password hash and a session record.
   The database is now ignored and removed from Git tracking, but old commits
   remain public.

3. In AWS IAM, deactivate and then delete the old access key. Removing it from
   Render or a local `.env` file does not revoke it. Also remove the two
   `AWS_*` lines still present in `backend/backend/.env` after the migration.

4. Purge `backend/db.sqlite3` and the historical hardcoded Django secret from
   Git history with `git filter-repo` or GitHub support, then force-push all
   branches and tags. Coordinate this because every clone must be recreated.
   Rotate credentials first; history rewriting is not a substitute for
   rotation.

5. In GitHub, inspect **Security > Secret scanning** and enable push protection
   for your account and repository.

## Render environment

Required:

```dotenv
SECRET_KEY=<new random value>
DEBUG=0
DATABASE_URL=<Neon connection string>
CLOUDINARY_URL=cloudinary://api_key:api_secret@cloud_name
FRONTEND_ORIGINS=https://vilu9169.github.io
ADMIN_PATH=<random non-obvious path>
SECURE_HSTS_SECONDS=31536000
```

Remove every `AWS_*` variable after Cloudinary is verified. Never place
Cloudinary, database, Django, or AWS secrets in `frontend/.env`, GitHub Actions
variables, or any variable beginning with `NEXT_PUBLIC_`.

Changing `ADMIN_PATH` reduces automated scans but is not authentication. Use a
unique password of at least 16 characters and do not reuse it anywhere.

## Provider cost controls

### Cloudinary

- Keep uploads signed and backend-only. Do not create an unsigned upload preset.
- Confirm billing email addresses and usage-warning emails.
- Review Usage Reports for bandwidth, transformations, and storage.
- Avoid unnecessary dynamic transformation variants. This application stores
  one thumbnail and one preview per photo.
- The free/self-service quota is soft: Cloudinary warns near the limit rather
  than immediately stopping service.

### Render

- Keep one fixed web-service instance and leave autoscaling disabled.
- Check **Billing** and the service **Metrics > Outbound Bandwidth** regularly.
- Set the Build Pipeline spend limit to zero if included build minutes are
  sufficient.
- Render's current Hobby allowance is 5 GB outbound per month; linked payment
  methods can be billed for overage.

### Neon

- Enable an organization spending limit from **Billing**.
- Confirm billing alert email addresses.
- Restrict database access where the plan supports it and keep automated
  backups enabled.

### AWS

- After validating Cloudinary, delete the S3 bucket only after retaining an
  offline backup.
- Delete unused IAM users/keys and configure a small AWS Budget alert while the
  account remains open.

## Application controls now present

- Production fails closed without `SECRET_KEY` or Render's `DATABASE_URL`.
- HTTPS redirect, HSTS, secure/HTTP-only cookies, and standard password
  validators are enabled.
- Staff authentication and CSRF protect upload, reorder, and delete actions.
- Public API requests are throttled and pagination values are bounded.
- Public API responses are briefly cacheable and do not initialize sessions.
- Uploads are limited to JPEG, PNG, or WebP, 20 MB, and 40 megapixels.
- Frontend production dependencies were updated and backend requirements have
  no known advisories according to `pip-audit`.
- SQLite databases, media, environment files, and Python bytecode are ignored.

## Remaining limitations

- Django admin has no multi-factor authentication or durable login rate limit.
  A custom domain behind Cloudflare Access, or a maintained Django MFA/login
  lockout package backed by Redis/Postgres, would materially improve this.
- GitHub Pages does not provide project-controlled response headers such as a
  Content Security Policy. A custom domain behind Cloudflare or another static
  host with configurable headers would improve browser hardening.
- Original Cloudinary assets are public if their URLs are known. Remove GPS and
  other sensitive EXIF metadata before uploading originals.
- Application throttling is per Render process. It reduces casual abuse but is
  not a replacement for an edge firewall.

## Verification

After deployment:

1. `https://photoport-v2-0.onrender.com/api/photos/` should return Cloudinary
   URLs, not `viktor-photo-media.s3.amazonaws.com`.
2. Response headers should include `Strict-Transport-Security`.
3. The old `/admin/` path should return 404 when a custom `ADMIN_PATH` is set.
4. Test one valid upload, one oversized upload, and deletion of the test asset.
5. Review Render, Neon, Cloudinary, AWS, and GitHub security/billing alerts.
