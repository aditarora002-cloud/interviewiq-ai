# InterviewIQ AI — Changelog

## Version 3.0 — Career OS

**Added:** Career OS dashboard and achievements; account-scoped applications pipeline; personal study tasks and roadmap from job-match skill gaps; deduplicating task imports; spaced-repetition flashcards and daily question evaluation; private profile editing, password changes, complete JSON exports and account deletion; interview question-to-flashcard action; cross-account isolation tests; Vercel deployment and QA guides.

**Improved:** Lower weight Python backend by replacing scikit-learn text similarity with a dependency-light TF-IDF cosine approximation. Frontend route and navigation integrated without replacing or removing the existing camera and grammar components. Production serverless startup now refuses to silently store accounts in ephemeral SQLite when `DATABASE_URL` is missing.

**Preserved:** Login/register/logout, resume and company matching, optional public research, interview questions and feedback, PDF reports, analytics, camera posture overlay, phone detection, speech-to-text and grammar coaching, monochrome visual system.

**Known limitations:** No verified full Vite build or webcam runtime test in this packaging environment; no live Vercel deployment; search needs Brave API; richer AI needs an OpenAI API key. Full public-launch authentication hardening is a separate security milestone.
