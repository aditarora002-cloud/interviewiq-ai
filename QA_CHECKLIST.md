# InterviewIQ AI 3.0 — Acceptance checklist

Run against a local frontend (`http://localhost:5173`) and backend (`http://127.0.0.1:8000`) before testing Vercel. **Do not overwrite your existing `interviewiq.db` without a backup.**

- [ ] Backend `/api/health` returns `status: ok`; the backend console has no startup exception.
- [ ] Register account A, log out, log in, reload browser; the workspace opens.
- [ ] In **Career OS**, the new metrics load and the links navigate to the correct page.
- [ ] In **Applications**, add an opportunity, edit its stage, change its next-action date, filter stage and delete it.
- [ ] In **Job Matcher**, paste a real description and obtain a sourced or clearly provisional match.
- [ ] In **My Roadmap**, click 'Add suggested steps' and see tasks; repeat and verify duplicate tasks are skipped. Mark one complete and reload.
- [ ] In **Flashcards**, create a card, reveal it, choose 'Good' and see its next-review date. Browse all cards.
- [ ] In **Daily Challenge**, choose a career field, answer the prompt and view feedback. Refresh and verify the prompt is stable for the same account/day/role.
- [ ] In **Mock Interview**, choose role, difficulty, level, round type and number of questions; verify buttons visibly show selected state and the session contains that count.
- [ ] Click 'Save to flashcards' on a mock question; check it is in the Flashcards page.
- [ ] In **Mock Interview**, use voice answer or type, submit, finish, download PDF report and view history.
- [ ] In **Camera & Speech Coach**, allow permissions, see moving pose landmarks, get *balanced* as well as improvement feedback and see phone-object model status. Never treat detection as proof of cheating.
- [ ] In **Resume Analyzer**, upload a PDF/DOCX/TXT and select the target job/company; view analysis and saved report.
- [ ] In **My Account**, update the name and export JSON. Change password and verify previous sessions are revoked.
- [ ] Create account B: ensure account A's reports, applications, tasks, cards and challenges are NOT accessible to B.
- [ ] Test browser mobile layout and keyboard input on form controls.
- [ ] From `backend/`: `python -m unittest -v test_interview_generation test_accounts_and_matching test_studio` passes.
- [ ] From `frontend/`: `npm install` followed by `npm run build` succeeds; no red errors in browser Console.
- [ ] Production only: register/login and reload at the Vercel URLs; saved data survives the next request/deployment, and browser camera loads with HTTPS permissions.

Release limitation: baseline backend tests and JSX syntax passed in the packaging environment, but npm registry DNS was unavailable there, so the full Vite production build and browser/hosting integration tests must be run on a machine with internet.
