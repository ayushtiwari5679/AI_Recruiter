# AI Recruiter — Sequential Candidate Screening

Recruiter/admin workflow MVP. Every stage is run separately so results can be reviewed and manually overridden before continuing.

## Flow
1. Upload candidate CSV.
2. Paste JD and run resume/JD evaluation.
3. Run GitHub analysis and calculate screening score.
4. Recruiter/admin reviews and edits scores/status in the table.
5. Upload test results CSV.
6. Review/edit final score and interview status.
7. Existing backend endpoints can send test emails and create Calendar/Meet interviews once credentials are configured.

## Candidate CSV
`name,email,college,branch,cgpa,best_ai_project,research_work,github_profile,resume_link`

## Test CSV
`email,test_la,test_code`

## Run backend
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```
API docs: `http://localhost:8000/docs`

## Run frontend
```powershell
cd frontend
npm install
npm run dev
```
Open the Vite URL, normally `http://localhost:5173`.

## Notes
- Current resume/JD stage uses the existing deterministic scoring service. Full remote resume download/parsing and LLM evaluation should be added before production submission.
- GitHub analysis uses public GitHub repository metadata.
- Manual edits are persisted to SQLite through `PATCH /candidates/{id}`.
- Authentication/role enforcement is not yet implemented; the UI is an admin/recruiter console, not a secure production RBAC system.

## v1.1 fixes
- Candidate and test-result uploads accept CSV, XLSX, and XLS.
- Duplicate emails inside one upload are skipped safely.
- Candidates already stored in SQLite are skipped instead of causing a 500 error.
- Admin/recruiter edits remain available through the frontend and PATCH endpoint.
- Sequential step result payloads are displayed correctly in the frontend.
