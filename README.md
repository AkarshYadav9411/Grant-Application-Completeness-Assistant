# Grant Application Completeness Assistant

## What this project does

This project helps review a draft grant application against a grant guideline.

You upload the guideline and the draft application, then the app extracts requirements, looks for supporting evidence in the application, flags missing or unclear items, and produces a completeness report.

It is not a funding decision tool. It is meant to help applicants or reviewers find gaps before submitting an application.

## Why I built it

Grant guidelines can be long, and it is easy to miss a required attachment, eligibility statement, budget detail, or formatting rule. I built this project to make that review process more structured and easier to repeat.

The main idea is simple: keep the AI focused on extraction and evidence mapping, then calculate the final completeness score with deterministic backend code.

## Main features

- Project workspaces for separate grant reviews.
- Guideline and draft application uploads.
- Versioned guideline and application documents.
- Text extraction from PDF, DOCX, TXT, and Markdown files.
- Requirement extraction from guideline text.
- Evidence mapping from draft application text.
- Statuses for supported, partially supported, missing, ambiguous, contradictory, rejected, and not applicable items.
- Clarification questions for items that need more information.
- Human review actions for confirming, rejecting, or editing AI mappings.
- Deterministic completeness scoring.
- Assessment history and stale assessment tracking when source material changes.
- Supporting document tracking.
- Markdown report export for the latest assessment.
- Mock AI provider for offline development and tests.
- Gemini provider for live AI calls.
- Docker Compose setup with PostgreSQL and the backend service.

## How it works

1. Upload a grant guideline.
2. Upload a draft application.
3. Extract requirements from the guideline.
4. Map evidence from the application to each requirement.
5. Identify missing, partial, ambiguous, or contradictory evidence.
6. Generate clarification questions for items that need follow-up.
7. Review AI mappings and confirm, reject, or edit them.
8. Calculate a deterministic completeness score.
9. Generate the final Markdown report.

## Tech stack

- Backend: FastAPI, SQLAlchemy 2.x async, Pydantic.
- Database: SQLite for local/offline testing, PostgreSQL with asyncpg for deployment.
- AI: Gemini through `google-generativeai`, plus a deterministic mock provider.
- Document processing: PyMuPDF, python-docx, python-magic.
- Frontend: React, TypeScript, Vite, Tailwind CSS, Axios, lucide-react.
- Tests: pytest, pytest-asyncio, Vitest, React Testing Library.
- Deployment: Docker and Docker Compose.

## Project structure

```text
.
|-- backend/
|   |-- app/
|   |   |-- ai/              # AI provider abstraction, prompts, mock/Gemini providers
|   |   |-- models/          # SQLAlchemy models
|   |   |-- routers/         # FastAPI routes
|   |   |-- schemas/         # Pydantic request/response models
|   |   |-- scoring/         # Deterministic completeness scoring
|   |   |-- services/        # Uploads, extraction, evidence mapping, reporting
|   |   |-- config.py        # Environment-based settings
|   |   |-- database.py      # Async SQLAlchemy setup
|   |   `-- main.py          # FastAPI app
|   |-- tests/               # Backend tests by phase
|   |-- Dockerfile
|   `-- requirements.txt
|-- frontend/
|   |-- src/
|   |   |-- components/      # Workspace UI components
|   |   |-- services/        # API client
|   |   |-- utils/           # Status helpers
|   |   `-- App.tsx
|   `-- package.json
|-- docker-compose.yml
|-- .env.example
`-- pytest.ini
```

## AI provider

The backend uses an AI provider abstraction. The app currently has:

- `mock`: deterministic, offline, used by tests.
- `gemini`: live provider using `GEMINI_API_KEY`.

For normal local development, `AI_PROVIDER=mock` is the easiest option. For real AI extraction and mapping, use `AI_PROVIDER=gemini`.

## Document processing

Supported upload formats:

- PDF
- DOCX
- TXT
- Markdown

The app extracts text and stores document chunks with source metadata such as page number, section, and chunk id. OCR is not used, so image-only PDFs are not supported.

## Scoring

The AI does not calculate the final score.

The backend scoring engine reads each requirement priority and effective evidence status, then calculates completeness deterministically:

- Supported evidence counts as full credit.
- Partially supported evidence counts as half credit.
- Missing, ambiguous, contradictory, and rejected evidence count as zero.
- Not applicable items are excluded from the denominator.
- Mandatory requirements carry more weight than recommended requirements.

The overall readiness status is also calculated in backend code.

## Running locally

### 1. Create a Python environment

From the project root:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

On macOS or Linux:

```bash
cd backend
python -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

### 2. Install frontend dependencies

From the project root:

```powershell
cd frontend
npm install
```

### 3. Create `.env`

Copy `.env.example` to `.env` and edit the values.

For simple local development with SQLite and the mock provider:

```env
APP_ENV=development
APP_DEBUG=true
AI_PROVIDER=mock
DATABASE_URL=sqlite:///./grant_assistant.db
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

Do not commit `.env`. It is already ignored by git.

### 4. Run the backend

From `backend/`:

```powershell
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

The backend will be available at:

```text
http://localhost:8000
```

Health check:

```text
http://localhost:8000/api/health
```

### 5. Run the frontend

From `frontend/`:

```powershell
npm run dev
```

The frontend will usually be available at:

```text
http://localhost:5173
```

### 6. Gemini configuration

To use Gemini instead of the mock provider, set:

```env
AI_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-1.5-flash
AI_TIMEOUT_SECONDS=45
```

Restart the backend after changing these values.

### 7. PostgreSQL setup without Docker

Create a PostgreSQL database and set `DATABASE_URL`:

```env
DATABASE_URL=postgresql+asyncpg://grant_assistant:your-password@localhost:5432/grant_assistant
```

The app also accepts a `postgresql://...` URL and converts it to the async SQLAlchemy form internally.

At the moment, the backend creates tables on startup through SQLAlchemy metadata. Alembic is included as a dependency, but this repo does not currently include migration scripts.

## Docker

The Docker setup runs PostgreSQL and the backend API.

Create a `.env` file first. Use safe values for local development and real secrets only in your private `.env`:

```env
POSTGRES_DB=grant_assistant
POSTGRES_USER=grant_assistant
POSTGRES_PASSWORD=change-this-password
DATABASE_URL=postgresql+asyncpg://grant_assistant:change-this-password@postgres:5432/grant_assistant
APP_ENV=production
APP_DEBUG=false
AI_PROVIDER=mock
```

Build and start:

```powershell
docker compose --env-file .env up --build
```

Run in the background:

```powershell
docker compose --env-file .env up -d --build
```

Check status:

```powershell
docker compose --env-file .env ps
```

Stop:

```powershell
docker compose --env-file .env down
```

Stop and remove volumes:

```powershell
docker compose --env-file .env down -v
```

The backend is exposed on:

```text
http://localhost:8000
```

The frontend is not currently included in `docker-compose.yml`; run it separately with `npm run dev` or build it with `npm run build`.

## API

Main API areas:

- `GET /api/health` - health check.
- `/api/projects` - create and list review projects.
- `/api/projects/{project_id}/guidelines` - upload and list guideline versions.
- `/api/projects/{project_id}/applications` - upload and list application versions.
- `/api/projects/{project_id}/requirements` - list and create requirements.
- `/api/projects/{project_id}/requirements/extract` - extract requirements from the latest guideline.
- `/api/projects/{project_id}/assess` - run evidence mapping and scoring.
- `/api/projects/{project_id}/assessment` - get the latest assessment.
- `/api/projects/{project_id}/assessments` - get assessment history.
- `/api/projects/{project_id}/assessment/report` - download the latest Markdown report.
- `/api/projects/{project_id}/evidence` - list evidence mappings.
- `/api/evidence/{evidence_id}` - edit reviewed evidence.
- `/api/evidence/{evidence_id}/confirm` - confirm a mapping.
- `/api/evidence/{evidence_id}/reject` - reject a mapping.
- `/api/projects/{project_id}/questions` - list clarification questions.
- `/api/questions/{question_id}` - update a clarification question.
- `/api/projects/{project_id}/documents` - manage supporting document metadata.

FastAPI also exposes interactive docs when the backend is running:

```text
http://localhost:8000/docs
```

## Tests

Backend tests:

```powershell
.\backend\venv\Scripts\python.exe -m pytest backend\tests
```

Frontend tests:

```powershell
cd frontend
npm test
```

Frontend production build:

```powershell
cd frontend
npm run build
```

## Current limitations

- OCR is not implemented.
- The Docker Compose file runs the backend and PostgreSQL, not the frontend.
- Alembic is installed, but migration files are not set up yet.
- The live AI provider currently implemented is Gemini. The mock provider is used for deterministic offline tests.
- The report export is Markdown, not PDF.
