# backend/api/routes/jobs.py
from fastapi import APIRouter, Depends, UploadFile, File
from typing import Optional, Dict
from backend.services.job_service import JobService

router = APIRouter()
job_service = JobService()

@router.post("/upload-job")
async def upload_job_description(
    job_title: str,
    company_name: str,
    location: str,
    posted_by: str,
    file: Optional[UploadFile] = File(None),
    job_text: Optional[str] = None
):
    return await job_service.upload_job_description(
        job_title, company_name, location, posted_by, file, job_text
    )

@router.get("/jobs")
async def get_all_jobs(status: Optional[str] = "active", limit: int = 20):
    return job_service.get_all_jobs(status, limit)