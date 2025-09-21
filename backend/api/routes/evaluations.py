# backend/api/routes/evaluations.py
from fastapi import APIRouter, Depends, Query
from typing import List, Optional, Dict
from backend.services.evaluation_service import EvaluationService

router = APIRouter()
evaluation_service = EvaluationService()

@router.get("/quiz/{quiz_id}")
async def get_quiz(quiz_id: str):
    return evaluation_service.get_quiz(quiz_id)

@router.post("/submit-quiz")
async def submit_quiz(
    quiz_id: str = Query(...),
    resume_id: str = Query(...),
    answers: List[int] = Query(...)
):
    return evaluation_service.submit_quiz(quiz_id, resume_id, answers)

@router.post("/evaluate-resume")
async def evaluate_single_resume(
    resume_id: str = Query(...),
    job_id: str = Query(...)
):
    return evaluation_service.evaluate_single_resume(resume_id, job_id)

@router.post("/evaluate-batch")
async def evaluate_batch_resumes(
    job_id: str = Query(...),
    resume_ids: Optional[List[str]] = None
):
    return evaluation_service.evaluate_batch_resumes(job_id, resume_ids)

@router.get("/job-evaluations/{job_id}")
async def get_job_evaluations(
    job_id: str,
    min_score: Optional[int] = None,
    verdict: Optional[str] = None
):
    return evaluation_service.get_job_evaluations(job_id, min_score, verdict)