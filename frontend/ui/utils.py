# frontend/ui/utils.py
import streamlit as st
import requests
from typing import List, Optional

API_BASE_URL = "http://localhost:8000/api"

def _headers():
    """Gets authentication headers for API requests."""
    headers = {}
    if st.session_state.get("api_key"):
        headers["X-API-Key"] = st.session_state["api_key"]
    return headers

def fetch_jobs(limit: int = 50) -> List[dict]:
    """Fetches a list of jobs from the API."""
    try:
        resp = requests.get(f"{API_BASE_URL}/jobs", params={"limit": limit}, timeout=8)
        if resp.ok:
            return resp.json().get("jobs", [])
    except requests.RequestException:
        pass
    return []

def fetch_resumes_api(limit: int = 10) -> List[dict]:
    """Fetches a list of resumes from the API."""
    try:
        # Corrected: Added headers=_headers() to include the API key
        resp = requests.get(f"{API_BASE_URL}/resumes", params={"limit": limit}, headers=_headers(), timeout=8)
        if resp.ok:
            return resp.json().get("resumes", [])
    except requests.RequestException:
        pass
    return []

def apply_to_job_api(job_id: str, file, candidate_email: str, candidate_name: str):
    """Submits a job application to the API."""
    files = {'file': (file.name, file.getvalue())}
    params = {'job_id': job_id, 'candidate_email': candidate_email, 'candidate_name': candidate_name}
    try:
        return requests.post(f"{API_BASE_URL}/apply", files=files, params=params, timeout=60)
    except requests.RequestException:
        return None

def create_job_api(job_text: str, job_title: str, company_name: str, location: str, posted_by: str):
    """Creates a new job posting via the API."""
    params = {
        'job_title': job_title,
        'company_name': company_name,
        'location': location,
        'posted_by': posted_by
    }
    try:
        # Send job_text as form data with key 'job_text_form' to match backend Form(...)
        form_data = {'job_text_form': job_text}
        return requests.post(
            f"{API_BASE_URL}/upload-job",
            params=params,
            headers=_headers(),
            data=form_data,
            timeout=30
        )
    except requests.RequestException:
        return None

def evaluate_single_api(resume_id: str, job_id: str):
    """Requests a single resume evaluation from the API."""
    params = {'resume_id': resume_id, 'job_id': job_id}
    try:
        return requests.post(f"{API_BASE_URL}/evaluate-resume", params=params, headers=_headers(), timeout=120)
    except requests.RequestException:
        return None

def evaluate_batch_api(job_id: str):
    """Requests a batch resume evaluation for a job from the API."""
    params = {'job_id': job_id}
    try:
        return requests.post(f"{API_BASE_URL}/evaluate-batch", params=params, headers=_headers(), timeout=600)
    except requests.RequestException:
        return None

def fetch_evaluations_api(job_id: str, min_score: Optional[int] = None, verdict: Optional[str] = None):
    """Fetches evaluation results for a job from the API."""
    params = {'min_score': min_score, 'verdict': verdict}
    # Filter out None values
    params = {k: v for k, v in params.items() if v is not None}
    try:
        return requests.get(f"{API_BASE_URL}/job-evaluations/{job_id}", params=params, headers=_headers(), timeout=30)
    except requests.RequestException:
        return None

def bulk_upload_resumes_api(job_id: str, files: List):
    """Submits multiple resumes for bulk upload."""
    upload_files = [('files', (file.name, file.getvalue())) for file in files]
    params = {'job_id': job_id}
    try:
        return requests.post(f"{API_BASE_URL}/bulk-upload-resumes", files=upload_files, params=params, headers=_headers(), timeout=300)
    except requests.RequestException:
        return None