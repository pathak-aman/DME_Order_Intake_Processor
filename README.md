# GenHealth DME Order Intake API

AI-native REST API for processing durable medical equipment (DME) orders from faxed PDFs.

## Live Demo

> **URL:** https://dme-order-intake-processor.vercel.app/
> **Dashboard:** https://dme-order-intake-processor.vercel.app/dashboard.html
> **API Docs (Swagger UI):** https://dme-order-intake-processor.vercel.app/docs
> **Health Check:** https://dme-order-intake-processor.vercel.app/health

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI (Python 3.11+) |
| Database | PostgreSQL (Neon.tech / Supabase) with SQLite local fallback |
| ORM | SQLAlchemy 2.0 |
| Auth | JWT (python-jose + passlib/bcrypt) |
| PDF Extraction | Google Gemini Flash (multimodal) |
| Deployment | Vercel (Python serverless + static frontend) |
| Frontend | Tailwind CSS + Lucide Icons + Vanilla JS |

---

## Project Structure

```
.
├── api/
│   ├── index.py          # Vercel Serverless Function entry point
│   ├── requirements.txt  # Python dependencies mirror
│   └── app/
│       ├── main.py       # FastAPI application factory & routes
│       ├── config.py     # Pydantic Settings with resilient defaults
│       ├── database.py   # SQLAlchemy engine & session factory
│       ├── models.py     # User & Order ORM models
│       ├── schemas.py    # Pydantic request/response validation
│       ├── auth.py       # JWT creation, hashing & auth dependency
│       └── routers/
│           ├── auth.py   # POST /auth/register, POST /auth/token
│           └── orders.py # Orders CRUD & POST /orders/upload
├── public/
│   ├── index.html        # Landing page (served at /)
│   └── dashboard.html    # DME Order Intake Dashboard (served at /dashboard.html)
├── requirements.txt      # Root dependencies for Vercel Python runtime
├── vercel.json           # Vercel serverless rewrites
├── .env.example
└── README.md
```

---

## Local Development

### 1. Prerequisites
- Python 3.10+
- (Optional) PostgreSQL database or local SQLite fallback

### 2. Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Mac/Linux

pip install -r requirements.txt
```

### 3. Environment Variables

Copy `.env.example` to `.env` in the project root:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (defaults to local SQLite if omitted) |
| `SECRET_KEY` | JWT signing secret |
| `GEMINI_API_KEY` | Google AI Studio key for document extraction (Phase 3) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime in minutes (default: `1440`) |

### 4. Run

```bash
uvicorn api.app.main:app --reload --port 8000
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

