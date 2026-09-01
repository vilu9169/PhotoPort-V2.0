# Viktor Lundin Photography

A public photography portfolio with a static Next.js frontend and a Django REST
API. The portfolio owns the photographs and upload workflow. The separate
[Photo Constellation](https://vilu9169.github.io/PhotoConstellation/) project
builds a visual-similarity map from the same public photo source.

## Architecture

```text
GitHub Pages frontend
        ↓
Public Django photo API
        ↓
Cloudinary image delivery

Public portfolio ──→ Photo Constellation
```

The portfolio and Photo Constellation remain independently deployable. Their
only integration is a public link and the documented photo API contract.

## Local development

Create local environment files from the tracked examples, then supply your own
development values:

```powershell
Copy-Item backend/backend/.env.example backend/backend/.env
Copy-Item frontend/.env.example frontend/.env.local
```

Run the backend:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip.exe install -r requirements.txt
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py runserver
```

Run the frontend in another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

## Configuration

Backend secrets belong in the hosting provider or an ignored local `.env`
file. See `backend/backend/.env.example` for the supported variable names.

Frontend variables are compiled into public browser code and must never contain
credentials:

- `NEXT_PUBLIC_API_URL` — public portfolio API origin
- `NEXT_PUBLIC_CONSTELLATION_URL` — public Photo Constellation site

The GitHub Pages workflow reads `NEXT_PUBLIC_API_URL` from a repository Actions
variable. The Photo Constellation link has a public default and can be
overridden for local development or forks.

## Deployment

Pushes to `main` build the static frontend and deploy it to GitHub Pages. The
Django backend is deployed separately and must provide the configured public
API origin. Uploaded photographs and credentials are not stored in this
repository.

## Public repository checklist

- Local `.env*` files, databases, uploaded media, and private keys are ignored.
- Only placeholder values are committed in `.env.example` files.
- GitHub Actions variables contain public frontend configuration only.
- Backend credentials remain in the deployment environment.
- Photo Constellation publishes visualization metadata, not model embeddings or
  Modal credentials.
