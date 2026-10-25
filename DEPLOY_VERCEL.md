# Deploy InterviewIQ AI 3.0 to Vercel — real accounts, real saved data

**Architecture:** two Vercel projects using a *single Git repository*, plus an external managed PostgreSQL database. A standalone Vite export **cannot** run the Python API or persist user accounts.

## Before you start

- Create a GitHub repository and push this project (you can upload through GitHub in a browser). Commit the `frontend`, `backend` and docs; **do not commit** any `.env`, `.db`, `.venv` or `node_modules`.
- Confirm `npm run build` succeeds in `frontend/` and all backend tests pass locally.
- Use a managed PostgreSQL instance from a reputable provider such as Neon or Supabase. Obtain its **server-side PostgreSQL connection string**, including required TLS/SSL parameters (a connection pooler is preferred if your provider recommends it for serverless traffic). Never paste this string into chat or public issues.
- Recommended: choose Python **3.12** for the backend runtime in Vercel settings if you get package compatibility problems.

## Project A — Backend / FastAPI

1. In Vercel, **Add New → Project → Import** your GitHub repository.
2. Set **Root Directory = `backend`**; **Framework Preset = FastAPI** if offered, otherwise let auto-detection find the Python entrypoint `backend/index.py` (`from app.main import app`). The root contains `requirements.txt`.
3. Set the following under **Project → Settings → Environment Variables** (Production; Preview too if you use preview):

   | Name | Value |
   |---|---|
   | `DATABASE_URL` | Your **private** hosted PostgreSQL connection string (required) |
   | `FRONTEND_ORIGIN` | `https://YOUR-FRONTEND.vercel.app` (exact origin, no trailing slash) |
   | `OPENAI_API_KEY` | Optional. Enables richer AI-generated questions and evaluation. |
   | `OPENAI_MODEL` | Optional; specify a model your provider account supports. |
   | `BRAVE_SEARCH_API_KEY` | Optional. Enables live public role/company research. |

4. Deploy. A missing `DATABASE_URL` will intentionally cause startup to fail on Vercel. Inspect deployment logs if that happens.
5. Verify `https://YOUR-BACKEND.vercel.app/api/health` gives JSON with `"status": "ok"`. This tests application startup, but **not** sign-in/database persistence yet.
6. Verify `https://YOUR-BACKEND.vercel.app/docs` loads the OpenAPI route descriptions. Avoid exposing production data in screenshots.

**Database setup:** SQLAlchemy creates required tables on application startup via `db.init()` and `studio.initialize()`. Tables are idempotent. For serious production deployments, move schema changes to managed migrations such as Alembic and apply them separately, rather than from cold-start web requests.

## Project B — Frontend / React + Vite

1. Vercel **Add New → Project** again, and import the **same** GitHub repository.
2. Set **Root Directory = `frontend`**; framework **Vite**, Build Command `npm run build`, Output Directory `dist`.
3. Add this **Environment Variable** to the frontend project:

   `VITE_API_URL=https://YOUR-BACKEND.vercel.app`

   Do **not** add `OPENAI_API_KEY`, `DATABASE_URL`, `BRAVE_SEARCH_API_KEY`, or passwords to the frontend variables.

4. Deploy. Check `https://YOUR-FRONTEND.vercel.app` displays the login screen.
5. If Vercel assigns a different frontend domain from the one configured in `FRONTEND_ORIGIN`, **edit the backend environment variable and redeploy the backend**. Don't include a path or trailing slash.
6. Whenever changing environment variables, **redeploy** the affected project so the new values apply.

## Mandatory end-to-end verification

Work from a normal or private Chrome/Edge window on the actual HTTPS frontend domain:

1. Register a new test account → log out → log back in (both operations should succeed).
2. Create a study task and opportunity → refresh the site → both must still exist.
3. Create a flashcard, reveal answer, rate it → due date updates.
4. Run a job match with a *real, pasted job description* → check missing skills → import suggested roadmap tasks.
5. Start a 3-question interview → submit at least one answer → finish → download its PDF report.
6. Enter the interview camera section and allow webcam/mic access. Verify the **pose model and phone model** show loaded, and move in and out of frame. Phone model failures may be CDN/model-specific, not Vercel API failures.
7. Open DevTools Console/Network and investigate any failed MediaPipe `.wasm` or `.tflite` URLs.
8. Open **My Account → Export my data** and check it contains your newly created records. Keep the downloaded file private.
9. Create a second account and confirm the first account's applications, resume analysis and task data are not shown to it.
10. Verify source links open actual company postings; research returns search snippets, **not** guaranteed full job descriptions.

## Common failures

| Symptom | Check |
|---|---|
| Backend crashes during deploy | Missing/invalid `DATABASE_URL`; PostgreSQL TLS requirements; Python package build; backend deployment logs |
| Frontend loads but calls fail | `VITE_API_URL` set to *backend* HTTPS origin; use Network tab; redeploy frontend after changing it |
| Browser reports CORS errors | `FRONTEND_ORIGIN` exactly matches frontend's scheme/domain/port; backend needs redeployment after env edits |
| Login succeeds but saved records disappear | You must connect hosted PostgreSQL; don't rely on serverless SQLite. Verify production and preview are using intended databases |
| Questions use fallback demo mode | Missing/invalid `OPENAI_API_KEY`, insufficient quota, or unavailable model/network |
| Company research returns no results | Configure private `BRAVE_SEARCH_API_KEY`; inspect search result status; paste actual job description |
| Camera permission blocked | Must be on HTTPS/localhost, user must allow webcam/microphone permissions |
| Phone detector says unavailable | Check model and WASM network requests in browser DevTools, not just FastAPI logs |

## Limitations and security before a public launch

- User records contain potentially sensitive resume and interview data. Set access controls and backups for your hosted database; adopt clear retention rules.
- Passwords are PBKDF2 hashed, and database-held session tokens are revocable. The client currently stores bearer tokens in browser `localStorage`; for a widely available service, migrate to secure, HttpOnly, SameSite cookies and CSRF safeguards as appropriate.
- Add centrally enforced sign-in throttling, brute-force protection, email verification, a safe password-reset service and usage quotas before a broad public launch. The current demo is not a security-audited commercial application.
- Model and search requests may incur charges and hit provider limits; monitor usage and budget with your provider. Service outages can make AI/search features fall back or become unavailable.
- The selfie/posture coach and phone detector are **not cheating or employment-suitability verdicts**. Candidates should consent before using the webcam. Browser speech recognition has browser-specific accuracy and privacy characteristics.
- Deployment from this ZIP has **not** been performed or verified on your Vercel account. These instructions provide a supported path, not a guarantee of zero deployment configuration work.

Official references:
- [Vercel: FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi)
- [Vercel: Vite on Vercel](https://vercel.com/docs/frameworks/frontend/vite)
- [Vercel: Environment variables](https://vercel.com/docs/environment-variables)
