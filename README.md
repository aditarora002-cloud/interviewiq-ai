# InterviewIQ AI 3.0 — Career Operating System

A full-stack career preparation studio: **React + Vite + TypeScript** frontend, **FastAPI + SQLAlchemy** backend, and SQLite locally or PostgreSQL in production. The app retains the existing *monochrome interview UI, resume analyzer, company/job matcher, authentication, saved reports, speech and grammar coach, real-time MediaPipe posture landmarks and optional phone-object detection*. This upgrade adds a **Career OS** with account-scoped planning and study tools.

## What's new in 3.0

| Feature | Where | Behaviour |
|---|---|---|
| Career OS | Career OS sidebar | Personal dashboard, completion metrics, practice streak and unlockable milestones |
| Application tracker | Applications | Save/edit/delete opportunities, stage filters, due dates, links and private notes |
| Evidence-based learning plan | My Roadmap | Convert the latest saved job-match missing-skills list into learning tasks; skip duplicates |
| Study task manager | My Roadmap | Create, complete, prioritise and delete tasks with optional deadlines |
| Spaced-repetition deck | Flashcards | Create cards, reveal answers, rate recall, schedule the next review |
| Interview → flashcards | Mock Interview | Save the current interview question and expected evaluation criteria into the deck |
| Daily question | Daily Challenge | Reproducible question for each account, calendar day and selected role; graded response and previous attempts |
| Private user data export | My Account | Download JSON containing your interviews, analyses, applications, tasks, cards and daily answers |
| Account controls | My Account | Update name, change password and revoke tokens; delete account and its records |
| Deployment-ready layout | `frontend/`, `backend/` | Two Vercel projects; PostgreSQL in production; lightweight Python similarity engine |

## 1. Run on Windows (PowerShell)

**First: protect your existing data.** Extract this ZIP to a *new folder*. If you want to keep accounts/history from your previous working project, stop your old backend and copy **`backend/interviewiq.db`** from your previous version into the new version's `backend/` folder **before starting the new backend**. Do not copy `node_modules` or `.venv`. Your old SQLite database is not included in this download. Back it up first.

**Terminal 1 — Backend** (run inside new `backend/`):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

This does not require activating PowerShell scripts. Visit <http://127.0.0.1:8000/api/health> and check that it responds.

**Terminal 2 — Frontend** (run inside new `frontend/`):

```powershell
npm install
npm run dev
```

Open <http://localhost:5173>, sign in or create a new account. Start with **Career OS**. Your existing **Mock Interview**, **Camera & Speech Coach**, **Resume Analyzer**, and **Job Matcher** remain on the sidebar.

## 2. Optional AI and company research

Create `backend/.env` by copying `backend/.env.example`, then fill in **only the keys you have permission to use**:

- `OPENAI_API_KEY` (optional) — richer, LLM-generated interview questions and answer feedback. Without it, role-specific questions and heuristic evaluation still run.
- `BRAVE_SEARCH_API_KEY` (optional) — public web search snippets for researched job matching. Without it, paste the actual job description yourself. Search snippets are not independently verified postings.

Never put secret keys in `frontend/.env` or a `VITE_` variable. **Job match percentages are rough resume-to-description text alignment**, not hiring probabilities or employer ATS scores.

The phone detector requires model resources to load over the internet and Chrome/Edge camera permissions; its detections and posture cues are approximations. Looking away and the mere presence of a phone do not establish cheating. The visual camera analysis remains browser-side in the existing implementation; browser-provided speech recognition may involve a third-party service.

## 3. Vercel deployment

See **[DEPLOY_VERCEL.md](DEPLOY_VERCEL.md)** for the end-to-end, two-project Vercel + hosted PostgreSQL guide and troubleshooting. Both frontend and backend can be hosted on Vercel, **but frontend-only drag and drop will not produce a working signed-in application**. Backend deployment without `DATABASE_URL` now fails immediately instead of quietly creating a nonpersistent SQLite database.

**Production requirements**: Hosted PostgreSQL, backend and frontend environment variables, HTTPS, browser camera permissions and model CDNs. Optional OpenAI and Brave Search keys unlock full AI/search integrations. The code was not actually deployed to Vercel in this packaging session; follow the deployment checklist to verify your account, save/reload, interview, research and camera experience.

For a **large public launch** beyond a student/demo project, additional security work remains: email verification, safe password recovery, shared rate limiting for logins and expensive model endpoints, anti-abuse controls, infrastructure monitoring and database backups. Current auth uses hashed passwords and revocable bearer tokens in `localStorage`; a hardened secure-cookie flow would be preferable for broad public use.

## 4. Tests

The original interview and account tests plus Studio contract tests are available:

```powershell
cd backend
.\.venv\Scripts\python.exe -m unittest -v test_interview_generation test_accounts_and_matching test_studio
```

Run a production frontend build before deployment:

```powershell
cd frontend
npm install
npm run build
```

See [QA_CHECKLIST.md](QA_CHECKLIST.md) for a repeatable full app acceptance test.

### Verification performed for this ZIP

- **16 backend unit/integration tests passed**, including multi-account data isolation and retention, applications, task planning, flashcards, challenge submissions, profile changes and data export/deletion.
- **Frontend TypeScript/JSX syntax parsing passed** for all changed source files using the TypeScript compiler API.
- **Not verified here**: complete production Vite build, Chrome camera/microphone runtime, Vercel deployment. The npm package registry was unreachable from the packaging environment; the ZIP contains source, not `node_modules`.

## Privacy

The application stores resume text, interview answers and other personal details under a user account in your database. Keep the database secure. Account export contains sensitive data. Do not put secrets or a production database in a public repository. Delete personal data when no longer needed and seek user consent before using camera/microphone features. This tool gives practice feedback, not professional hiring guarantees.
