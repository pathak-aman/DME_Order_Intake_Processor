# GenHealth DME Order Intake API

AI-native REST API for processing durable medical equipment (DME) orders from faxed PDFs.

## Live Demo

> **URL:** _(add Vercel URL after deploy)_
> **API Docs:** `<URL>/docs`

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI (Python 3.11+) |
| Database | PostgreSQL (Neon.tech free tier) |
| ORM | SQLAlchemy 2.0 |
| Auth | JWT (python-jose + passlib/bcrypt) |
| PDF Extraction | Google Gemini Flash (multimodal) |
| Deployment | Vercel (Python serverless + static frontend) |
| Frontend | Vanilla JS + Tailwind CSS |

---

## Project Structure

```
.
├── api/
│   └── index.py          # Vercel Python entry point
├── backend/
│   ├── app/
│   │   ├── main.py       # FastAPI app factory
│   │   ├── config.py     # Settings (pydantic-settings)
│   │   ├── database.py   # SQLAlchemy engine
│   │   ├── models.py     # User, Order ORM models
│   │   ├── schemas.py    # Pydantic request/response schemas
│   │   ├── auth.py       # JWT + password hashing
│   │   └── routers/
│   │       ├── auth.py   # /auth/register, /auth/token
│   │       └── orders.py # CRUD + /orders/upload
│   └── requirements.txt
├── frontend/
│   └── index.html        # Single-page dashboard UI
├── vercel.json
├── .env.example
└── README.md
```

---

## Local Development

### 1. Prerequisites
- Python 3.11+
- PostgreSQL database (or free [Neon.tech](https://neon.tech) account)

### 2. Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Mac/Linux

pip install -r requirements.txt
```

### 3. Environment Variables

Copy `.env.example` to `.env` in the project root and fill in values:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `SECRET_KEY` | Random secret: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | PostgreSQL URL, e.g. `postgresql://user:pass@host/dbname` |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com) API key |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT expiry (default: `60`) |

### 4. Run

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

- API docs: http://localhost:8000/docs
- Frontend: open `frontend/index.html` in browser, set API host to `http://localhost:8000`

---

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | No | Health check |
| `POST` | `/auth/register` | No | Create account |
| `POST` | `/auth/token` | No | Login → JWT |
| `GET` | `/orders/` | Bearer | List my orders |
| `POST` | `/orders/` | Bearer | Create order manually |
| `GET` | `/orders/{id}` | Bearer | Get single order |
| `PUT` | `/orders/{id}` | Bearer | Update order |
| `DELETE` | `/orders/{id}` | Bearer | Delete order |
| `POST` | `/orders/upload` | Bearer | Upload PDF → extract fields |

---

## Deployment (Vercel)

### Prerequisites
- [Vercel account](https://vercel.com) (free)
- [Neon.tech](https://neon.tech) free PostgreSQL (or Vercel Postgres)
- GitHub repository

### Steps

1. Push this repo to GitHub
2. Import project in Vercel dashboard
3. Set environment variables in Vercel → Project → Settings → Environment Variables:
   - `SECRET_KEY`
   - `DATABASE_URL`
   - `GEMINI_API_KEY`
4. Deploy → Vercel auto-detects `vercel.json`

---

## Example cURL Commands

```bash
# Register
curl -X POST https://<your-url>/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"secret123"}'

# Login
curl -X POST https://<your-url>/auth/token \
  -d "username=test@example.com&password=secret123"

# List orders (replace TOKEN)
curl https://<your-url>/orders/ \
  -H "Authorization: Bearer TOKEN"

# Upload PDF
curl -X POST https://<your-url>/orders/upload \
  -H "Authorization: Bearer TOKEN" \
  -F "file=@DME_Patient_Demo_Document_CPAP.fax.pdf"
```
