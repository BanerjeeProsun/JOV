"""Hostile Mock Portal (Blueprint v2.0 Section 10).

Runs on 127.0.0.1:8765 only.
Provides career pages, hostile fault modes, status lookup, and ground-truth oracle.
"""

import asyncio
from datetime import datetime
import uuid
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Form, File, UploadFile, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel


app = FastAPI(title="JOV.si Hostile Mock Portal", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# In-memory storage for ground truth oracle
oracle_applications: List[Dict[str, Any]] = []
active_fault: Optional[str] = None
last_submit_timestamp: Optional[float] = None


class FaultConfig(BaseModel):
    fault_mode: Optional[str] = None  # slow_submit, drop_after_submit, reject_without_record, etc.


@app.post("/__admin/fault")
def set_fault(config: FaultConfig) -> Dict[str, Any]:
    global active_fault
    active_fault = config.fault_mode
    return {"status": "ok", "active_fault": active_fault}


@app.get("/__admin/applications")
def get_oracle_applications() -> List[Dict[str, Any]]:
    """Ground-truth oracle: portal's actual stored applications."""
    return oracle_applications


@app.post("/__admin/reset")
def reset_mock_portal() -> Dict[str, Any]:
    global active_fault, last_submit_timestamp
    oracle_applications.clear()
    active_fault = None
    last_submit_timestamp = None
    return {"status": "reset_complete"}


@app.get("/jobs/{job_id}")
def view_job(job_id: str) -> HTMLResponse:
    global active_fault
    if active_fault == "job_404":
        active_fault = None
        raise HTTPException(status_code=404, detail="Job not found")

    html = f"""
    <!DOCTYPE html>
    <html>
    <head><title>Job {job_id} | Acme Mock Corp</title></head>
    <body style="font-family: sans-serif; padding: 20px;">
        <h1 data-testid="job-title">Senior Python Architect</h1>
        <h2 data-testid="company-name">Acme Corp</h2>
        <p>Location: Remote</p>
        <p>Requirements: Python, FastAPI, SQL</p>
        <a href="/jobs/{job_id}/apply" data-testid="apply-button">Apply Now</a>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.get("/jobs/{job_id}/apply")
def apply_form(job_id: str) -> HTMLResponse:
    global active_fault
    if active_fault == "job_404":
        active_fault = None
        raise HTTPException(status_code=404, detail="Job not found")

    if active_fault == "session_expired":
        active_fault = None
        return RedirectResponse(url="/login", status_code=302)

    if active_fault == "captcha_required":
        active_fault = None
        return RedirectResponse(url="/captcha", status_code=302)

    if active_fault == "already_applied_warning":
        active_fault = None
        return HTMLResponse(
            status_code=200,
            content="<html><body><div data-testid='already-applied'>You have already applied for this position.</div></body></html>",
        )

    # DOM Drift fault: alter fields unexpectedly
    is_drift = (active_fault == "dom_drift")
    if is_drift:
        active_fault = None
        # Renamed field and new unexpected required field
        form_fields_html = """
        <label for="f_name">Candidate Legal Name</label>
        <input type="text" id="f_name" name="legal_name" required /><br/><br/>
        
        <label for="gov_id">National ID Number (Required)</label>
        <input type="text" id="gov_id" name="gov_id" required /><br/><br/>
        """
    else:
        form_fields_html = """
        <label for="full_name">Full Name</label>
        <input type="text" id="full_name" name="full_name" data-testid="field-name" required /><br/><br/>

        <label for="email">Email Address</label>
        <input type="email" id="email" name="email" data-testid="field-email" required /><br/><br/>

        <label for="phone">Phone Number</label>
        <input type="tel" id="phone" name="phone" data-testid="field-phone" required /><br/><br/>

        <label for="experience_years">Years of Experience</label>
        <input type="number" id="experience_years" name="experience_years" data-testid="field-exp" required /><br/><br/>

        <label for="work_auth">Work Authorization</label>
        <select id="work_auth" name="work_auth" data-testid="field-work-auth">
            <option value="YES">Authorized to work</option>
            <option value="NO">Not authorized</option>
        </select><br/><br/>

        <label for="sponsorship">Sponsorship Required</label>
        <select id="sponsorship" name="sponsorship" data-testid="field-sponsorship">
            <option value="NO">No sponsorship needed</option>
            <option value="YES">Requires sponsorship</option>
        </select><br/><br/>

        <label for="eeo_gender">Gender (Optional)</label>
        <select id="eeo_gender" name="eeo_gender" data-testid="field-eeo">
            <option value="DECLINE">Decline to self-identify</option>
            <option value="FEMALE">Female</option>
            <option value="MALE">Male</option>
        </select><br/><br/>

        <label for="legal_attestation">
            <input type="checkbox" id="legal_attestation" name="legal_attestation" value="agree" data-testid="field-attestation" required />
            I certify that all statements made in this application are true and correct.
        </label><br/><br/>

        <label for="resume">Resume (PDF)</label>
        <input type="file" id="resume" name="resume" accept=".pdf" data-testid="field-resume" required /><br/><br/>

        <label for="cover_letter">Cover Letter (Optional)</label>
        <input type="file" id="cover_letter" name="cover_letter" accept=".pdf" data-testid="field-cover-letter" /><br/><br/>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head><title>Apply for Job {job_id} | Acme Corp</title></head>
    <body style="font-family: sans-serif; padding: 20px;">
        <h1 data-testid="apply-role-title">Senior Python Architect</h1>
        <h2 data-testid="apply-company-title">Acme Corp</h2>
        <form action="/jobs/{job_id}/apply" method="POST" enctype="multipart/form-data" data-testid="apply-form">
            {form_fields_html}
            <button type="submit" data-testid="submit-btn" style="padding: 10px 20px; font-weight: bold;">Submit Application</button>
        </form>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.post("/jobs/{job_id}/apply")
async def handle_submit(
    job_id: str,
    request: Request,
    full_name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    experience_years: Optional[str] = Form(None),
    work_auth: Optional[str] = Form(None),
    sponsorship: Optional[str] = Form(None),
    eeo_gender: Optional[str] = Form(None),
    legal_attestation: Optional[str] = Form(None),
    resume: Optional[UploadFile] = File(None),
    cover_letter: Optional[UploadFile] = File(None),
) -> Any:
    global active_fault, last_submit_timestamp
    current_time = datetime.utcnow().timestamp()

    # Fault: double_click within 2s
    if active_fault == "double_click":
        if last_submit_timestamp and (current_time - last_submit_timestamp) < 2.0:
            active_fault = None
            raise HTTPException(status_code=409, detail="Duplicate submission detected within 2 seconds")
    last_submit_timestamp = current_time

    # Fault: slow_submit
    if active_fault == "slow_submit":
        active_fault = None
        await asyncio.sleep(5.0)  # Delayed response

    # Fault: server_validation_error
    if active_fault == "server_validation_error":
        active_fault = None
        raise HTTPException(status_code=400, detail="Server validation error: Email domain is not accepted")

    # Fault: reject_without_record (500, nothing saved)
    if active_fault == "reject_without_record":
        active_fault = None
        raise HTTPException(status_code=500, detail="Internal Server Error: Database failure")

    # Fault: already_applied_warning
    if active_fault == "already_applied_warning":
        active_fault = None
        return HTMLResponse(
            status_code=200,
            content="<html><body><div data-testid='already-applied'>You have already applied for this position.</div></body></html>",
        )

    ref_num = f"ACM-{uuid.uuid4().hex[:8].upper()}"

    # Fault: lying_confirmation (shows success, saves NOTHING to oracle)
    if active_fault == "lying_confirmation":
        active_fault = None
        return RedirectResponse(url=f"/confirmation/{ref_num}?job_id={job_id}&email={email or ''}", status_code=303)

    # Save to oracle
    resume_filename = resume.filename if resume else None
    app_record = {
        "ref": ref_num,
        "job_id": job_id,
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "experience_years": experience_years,
        "work_auth": work_auth,
        "sponsorship": sponsorship,
        "legal_attestation": legal_attestation,
        "resume_filename": resume_filename,
        "submitted_at": datetime.utcnow().isoformat(),
    }
    oracle_applications.append(app_record)

    # Fault: drop_after_submit (saved to oracle, connection dropped)
    if active_fault == "drop_after_submit":
        active_fault = None
        # Close connection abruptly
        raise HTTPException(status_code=502, detail="Connection reset by peer after write")

    return RedirectResponse(url=f"/confirmation/{ref_num}?job_id={job_id}&email={email or ''}", status_code=303)


@app.get("/confirmation/{ref}")
def confirmation_page(ref: str, job_id: str = "mock-1", email: str = "") -> HTMLResponse:
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><title>Application Received | Acme Corp</title></head>
    <body style="font-family: sans-serif; padding: 20px;">
        <h1 data-testid="receipt-title">Application Submitted!</h1>
        <p>Thank you for applying to Acme Corp.</p>
        <p>Your confirmation reference is: <strong data-testid="confirmation-ref">{ref}</strong></p>
        <p data-testid="receipt-role">Senior Python Architect</p>
        <p data-testid="receipt-company">Acme Corp</p>
        <p data-testid="receipt-email">{email}</p>
        <a href="/status?ref={ref}&email={email}" data-testid="status-link">Check Status</a>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.get("/status")
def status_lookup(ref: str, email: str) -> HTMLResponse:
    """Independent status lookup endpoint used for E3 evidence."""
    match = next((a for a in oracle_applications if a["ref"] == ref and a.get("email") == email), None)
    if match:
        html = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Application Status | Acme Corp</title></head>
        <body>
            <h1 data-testid="status-header">Application Confirmed</h1>
            <p>Reference: <span data-testid="status-ref">{match['ref']}</span></p>
            <p>Status: <span data-testid="status-value">Under Review</span></p>
            <p>Candidate: <span data-testid="status-email">{match['email']}</span></p>
        </body>
        </html>
        """
        return HTMLResponse(content=html)
    else:
        return HTMLResponse(
            status_code=404,
            content="<html><body><h1>No application found for this reference and email.</h1></body></html>",
        )


@app.get("/login")
def login_page() -> HTMLResponse:
    return HTMLResponse("<html><body><h1>Please Log In to Continue</h1><div data-testid='login-wall'>Login Wall</div></body></html>")


@app.get("/captcha")
def captcha_page() -> HTMLResponse:
    return HTMLResponse("<html><body><h1>Human Verification Required</h1><div data-testid='captcha-challenge'>CAPTCHA</div></body></html>")
