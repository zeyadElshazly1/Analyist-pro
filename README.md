# Analyst Pro

Turn messy client spreadsheets into client-ready analysis. Upload CSV or Excel files, auto-clean the data, spot issues and trends, compare versions, and export polished reports.

## Apps

- `apps/web` — Next.js 14 frontend
- `apps/api` — FastAPI backend

## Quick Start

### API (backend)

```bash
cd apps/api
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows:
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
cp .env.example .env   # fill in SUPABASE_URL, SUPABASE_JWT_SECRET, DATABASE_URL

alembic upgrade head
uvicorn app.main:app --reload --port 8000 --reload-dir app
```

### Web (frontend)

```bash
cd apps/web
npm install
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

## Environment Variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_JWT_SECRET` | Supabase JWT secret for auth verification |
| `UPLOAD_DIR` | Local path for uploaded files (default: `./uploads`) |
| `ALLOWED_ORIGINS` | Comma-separated list of allowed CORS origins (default: `http://localhost:3000`) |
| `ANTHROPIC_API_KEY` | Anthropic API key for AI features |

## Features

- Smart file ingestion (CSV, Excel, multi-sheet, preamble detection)
- Automated data cleaning with audit trail
- AI-powered insights and narrative generation
- File comparison (month-over-month, version diff)
- Report builder with PDF and Excel export
- Guided 6-step consultant workflow
