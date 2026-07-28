from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import pandas as pd
import io

from .database import Base, engine, get_db
from .models import Candidate
from .services.scoring import explain_match, screening_score, final_score
from .services.github import analyze_github
from .services.emailer import send_email
from .services.calendar import create_interview

Base.metadata.create_all(bind=engine)
app = FastAPI(title="myNachiketa Sequential Candidate Screening", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FIELDS = ["id", "name", "email", "college", "branch", "cgpa", "best_ai_project", "research_work", "github_profile", "resume_link", "resume_text", "resume_score", "github_score", "screening_score", "logical_score", "coding_score", "final_score", "status"]

def out(c):
    return {k: getattr(c, k) for k in FIELDS}

def clean_value(value, default=""):
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    return value

def normalize_email(value):
    return str(clean_value(value, "")).strip().lower()

def safe_float(value, default=0.0):
    try:
        return float(clean_value(value, default))
    except (ValueError, TypeError):
        return default

async def read_table(file: UploadFile):
    content = await file.read()
    if not content:
        raise HTTPException(400, "Uploaded file is empty.")
    name = (file.filename or "").lower()
    try:
        if name.endswith(".csv"):
            return pd.read_csv(io.BytesIO(content))
        if name.endswith(".xlsx"):
            return pd.read_excel(io.BytesIO(content), engine="openpyxl")
        if name.endswith(".xls"):
            return pd.read_excel(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(400, f"Unable to read uploaded file: {e}")
    raise HTTPException(400, "Supported files: .csv, .xlsx, .xls")

class CandidateEdit(BaseModel):
    name: str | None = None
    email: str | None = None
    college: str | None = None
    branch: str | None = None
    cgpa: float | None = None
    best_ai_project: str | None = None
    research_work: str | None = None
    github_profile: str | None = None
    resume_link: str | None = None
    resume_score: float | None = None
    github_score: float | None = None
    screening_score: float | None = None
    logical_score: float | None = None
    coding_score: float | None = None
    final_score: float | None = None
    status: str | None = None

    @app.get("/health")
    def health():return {"status": "ok","version": "2.0","message": "Backend updated successfully"}

@app.post("/candidates/upload")
async def upload_candidates(file: UploadFile = File(...), db: Session = Depends(get_db)):
    df = await read_table(file)
    if df.empty:
        raise HTTPException(400, "Candidate dataset contains no rows.")
    norm = {str(c).lower().strip().replace(" ", "_"): c for c in df.columns}
    if "email" not in norm:
        raise HTTPException(400, "Dataset must contain an email column.")

    def g(row, name, default=""):
        col = norm.get(name)
        return clean_value(row.get(col, default), default) if col is not None else default

    added = skipped = invalid = duplicate_in_file = already_exists = 0
    processed = set()
    try:
        for _, row in df.iterrows():
            email = normalize_email(g(row, "email"))
            if not email:
                invalid += 1; skipped += 1; continue
            if email in processed:
                duplicate_in_file += 1; skipped += 1; continue
            processed.add(email)

            existing = db.query(Candidate).filter(Candidate.email == email).first()
            if existing:
                existing.name = str(g(row, "name")).strip()
                existing.college = str(g(row, "college")).strip()
                existing.branch = str(g(row, "branch")).strip()
                existing.cgpa = safe_float(g(row, "cgpa", 0))
                existing.best_ai_project = str(g(row, "best_ai_project")).strip()
                existing.research_work = str(g(row, "research_work")).strip()
                existing.github_profile = str(g(row, "github_profile")).strip()
                existing.resume_link = str(g(row, "resume_link")).strip()

                already_exists += 1
                continue
            db.add(Candidate(
                name=str(g(row, "name")).strip(),
                email=email,
                college=str(g(row, "college")).strip(),
                branch=str(g(row, "branch")).strip(),
                cgpa=safe_float(g(row, "cgpa", 0)),
                best_ai_project=str(g(row, "best_ai_project")).strip(),
                research_work=str(g(row, "research_work")).strip(),
                github_profile=str(g(row, "github_profile")).strip(),
                resume_link=str(g(row, "resume_link")).strip(),
                status="uploaded"
            ))
            db.flush()
            added += 1
        db.commit()
    except IntegrityError as e:
        db.rollback(); raise HTTPException(409, f"Duplicate candidate conflict: {e.orig}")
    except Exception as e:
        db.rollback(); raise HTTPException(500, f"Candidate upload failed: {e}")
    return {"success": True, "total_rows": len(df), "added": added, "skipped": skipped, "invalid": invalid, "duplicate_in_file": duplicate_in_file, "already_exists": already_exists, "next_step": "resume_jd"}

@app.get("/candidates")
def get_candidates(db: Session = Depends(get_db)):
    return [out(c) for c in db.query(Candidate).order_by(Candidate.id).all()]

@app.get("/candidates/{cid}")
def get_candidate(cid: int, db: Session = Depends(get_db)):
    c = db.get(Candidate, cid)
    if not c: raise HTTPException(404, "Candidate not found")
    return out(c)

@app.patch("/candidates/{cid}")
def edit_candidate(cid: int, body: CandidateEdit, db: Session = Depends(get_db)):
    c = db.get(Candidate, cid)
    if not c: raise HTTPException(404, "Candidate not found")
    updates = body.model_dump(exclude_none=True)
    if "email" in updates:
        email = normalize_email(updates["email"])
        if not email: raise HTTPException(400, "Email cannot be empty")
        duplicate = db.query(Candidate).filter(Candidate.email == email, Candidate.id != cid).first()
        if duplicate: raise HTTPException(409, "Another candidate already uses this email")
        updates["email"] = email
    for k, v in updates.items(): setattr(c, k, v)
    try:
        db.commit(); db.refresh(c)
    except IntegrityError:
        db.rollback(); raise HTTPException(409, "Candidate update conflicts with existing data")
    return out(c)

@app.delete("/candidates/{cid}")
def delete_candidate(cid: int, db: Session = Depends(get_db)):
    c = db.get(Candidate, cid)
    if not c: raise HTTPException(404, "Candidate not found")
    db.delete(c); db.commit()
    return {"success": True, "candidate_id": cid}

@app.post("/steps/resume-jd")
def resume_jd(job_description: str = Form(...), db: Session = Depends(get_db)):
    if not job_description.strip(): raise HTTPException(400, "Job description cannot be empty")
    candidates = db.query(Candidate).all()
    if not candidates: raise HTTPException(400, "Upload candidates first")
    results = []
    try:
        for c in candidates:
            text = " ".join([c.best_ai_project or "", c.research_work or "", c.resume_text or "", c.branch or "", c.college or ""])
            ev = explain_match(text, job_description)
            c.resume_score = safe_float(ev.get("score", 0)); c.status = "resume_reviewed"
            results.append({"id": c.id, "candidate": c.name, "email": c.email, "resume_score": c.resume_score, "evaluation": ev, "status": c.status})
        db.commit()
    except Exception as e:
        db.rollback(); raise HTTPException(500, f"Resume/JD evaluation failed: {e}")
    return {"success": True, "evaluated": len(results), "next_step": "github", "results": results}

@app.post("/steps/github")
async def github_step(db: Session = Depends(get_db)):
    candidates = db.query(Candidate).all()
    if not candidates: raise HTTPException(400, "No candidates available")
    results = []
    for c in candidates:
        try:
            if not c.github_profile:
                gh = {
                    "score": 0,
                    "error": "Missing GitHub profile"
                }
                gh_score = 0
            else:
                gh = await analyze_github(c.github_profile)
                gh_score = safe_float(gh.get("score", 0))
        except Exception as e:
            gh = {"score": 0, "error": str(e)}; gh_score = 0
        c.github_score = gh_score
        c.screening_score = screening_score(c.resume_score or 0, c.github_score or 0, c.cgpa or 0)
        c.status = "shortlisted" if c.screening_score >= 65 else "screened"
        results.append({"id": c.id, "candidate": c.name, "email": c.email, "github": gh, "screening_score": c.screening_score, "status": c.status})
    db.commit(); results.sort(key=lambda x: x["screening_score"] or 0, reverse=True)
    return {"success": True, "evaluated": len(results), "next_step": "recruiter_review", "results": results}

@app.post("/tests/upload")
async def upload_tests(file: UploadFile = File(...), db: Session = Depends(get_db)):
    df = await read_table(file)
    norm = {str(c).lower().strip().replace(" ", "_"): c for c in df.columns}
    missing = [c for c in ["email", "test_la", "test_code"] if c not in norm]
    if missing: raise HTTPException(400, "Missing test result columns: " + ", ".join(missing))
    updated = not_found = 0; results = []
    try:
        for _, row in df.iterrows():
            email = normalize_email(row.get(norm["email"], ""))
            c = db.query(Candidate).filter(Candidate.email == email).first()
            if not c: not_found += 1; continue
            c.logical_score = safe_float(row.get(norm["test_la"], 0)); c.coding_score = safe_float(row.get(norm["test_code"], 0))
            c.final_score = final_score(c.screening_score or 0, c.logical_score, c.coding_score)
            c.status = "interview" if c.final_score >= 70 else "rejected"; updated += 1
            results.append({"id": c.id, "candidate": c.name, "email": c.email, "logical_score": c.logical_score, "coding_score": c.coding_score, "final_score": c.final_score, "status": c.status})
        db.commit()
    except Exception as e:
        db.rollback(); raise HTTPException(500, f"Test result processing failed: {e}")
    results.sort(key=lambda x: x["final_score"] or 0, reverse=True)
    return {"success": True, "updated": updated, "not_found": not_found, "next_step": "final_review", "results": results}

@app.get("/rankings")
def rankings(db: Session = Depends(get_db)):
    rows = db.query(Candidate).order_by(Candidate.final_score.desc()).all()
    return [{**out(c), "rank": i} for i, c in enumerate(rows, 1)]

@app.post("/candidates/{cid}/send-test")
def send_test(cid: int, test_link: str = Form(...), db: Session = Depends(get_db)):
    c = db.get(Candidate, cid)
    if not c: raise HTTPException(404, "Candidate not found")
    if not test_link.strip(): raise HTTPException(400, "Test link cannot be empty")
    result = send_email(c.email, "Technical Assessment Invitation", f"Hello {c.name},\n\nYou have been shortlisted. Complete your assessment here: {test_link}\n")
    c.status = "test_sent"; db.commit()
    return {"success": True, "candidate": c.name, "email": c.email, "status": c.status, "email_result": result}

@app.post("/candidates/{cid}/schedule")
def schedule(cid: int, start_iso: str = Form(...), end_iso: str = Form(...), db: Session = Depends(get_db)):
    c = db.get(Candidate, cid)
    if not c: raise HTTPException(404, "Candidate not found")
    try:
        interview = create_interview(c.email, start_iso, end_iso, c.name)
        if not interview.get("created"):
            raise HTTPException(503, interview.get("reason", "Calendar event was not created"))
        c.status = "interview_scheduled"; db.commit()
        return {"success": True, "candidate": c.name, "email": c.email, "status": c.status, "interview": interview}
    except Exception as e:
        db.rollback(); raise HTTPException(500, f"Unable to schedule interview: {e}")

class BulkInterviewRequest(BaseModel):
    start_iso: str
    duration_minutes: int = 30
    gap_minutes: int = 10
    statuses: list[str] = ["selected", "interview"]

@app.post("/interviews/schedule-automatic")
def schedule_interviews_automatic(body: BulkInterviewRequest, db: Session = Depends(get_db)):
    """Schedule selected/interview candidates sequentially and let Google Calendar email Meet invitations."""
    from datetime import datetime, timedelta
    try:
        start = datetime.fromisoformat(body.start_iso.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(400, "start_iso must be an ISO date/time, e.g. 2026-07-30T10:00:00+05:30")
    if body.duration_minutes < 10 or body.gap_minutes < 0:
        raise HTTPException(400, "duration_minutes must be >= 10 and gap_minutes >= 0")

    rows = db.query(Candidate).filter(Candidate.status.in_(body.statuses)).order_by(Candidate.final_score.desc()).all()
    if not rows:
        raise HTTPException(400, "No candidates with the selected statuses are available to schedule")

    results = []
    current = start
    for c in rows:
        end = current + timedelta(minutes=body.duration_minutes)
        try:
            interview = create_interview(c.email, current.isoformat(), end.isoformat(), c.name)
            if interview.get("created"):
                c.status = "interview_scheduled"
                results.append({"id": c.id, "candidate": c.name, "email": c.email, "scheduled": True, "interview": interview})
            else:
                results.append({"id": c.id, "candidate": c.name, "email": c.email, "scheduled": False, "error": interview.get("reason")})
        except Exception as e:
            results.append({"id": c.id, "candidate": c.name, "email": c.email, "scheduled": False, "error": str(e)})
        current = end + timedelta(minutes=body.gap_minutes)
    db.commit()
    return {"success": True, "scheduled": sum(1 for x in results if x["scheduled"]), "total": len(results), "results": results}
