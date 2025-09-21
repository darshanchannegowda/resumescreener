# backend/api/routes/resumes.py
from fastapi import APIRouter, UploadFile, File, Query, Depends
from typing import Optional, Dict
from backend.services.resume_service import ResumeService

router = APIRouter()
resume_service = ResumeService()

@router.post("/apply")
async def apply_for_job(
    job_id: str = Query(...),
    file: UploadFile = File(...),
    candidate_email: str = Query(...),
    candidate_name: Optional[str] = None
):
    return await resume_service.apply_for_job(
        job_id, file, candidate_email, candidate_name
    )

@router.post("/upload-resume")
async def upload_resume(
    file: UploadFile = File(...),
    candidate_email: str = Query(...),
    candidate_name: Optional[str] = None
):
    return await resume_service.upload_resume(file, candidate_email, candidate_name)

@router.get("/resumes")
async def get_all_resumes(
    limit: int = 10
):
    return resume_service.get_all_resumes(limit)