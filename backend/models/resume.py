from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class Resume(BaseModel):
    candidate_name: Optional[str] = None
    candidate_email: Optional[EmailStr] = None
    phone: Optional[str] = None
    location: Optional[str] = None

    # Parsed sections
    education: List[Dict[str, Any]] = []
    experience: List[Dict[str, Any]] = []
    skills: List[str] = []
    projects: List[Dict[str, Any]] = []
    certifications: List[str] = []

    # Raw and processed text
    raw_text: Optional[str] = ""
    processed_text: Optional[str] = ""

    # Embeddings (list of floats)
    embeddings: Optional[List[float]] = None

    # Metadata
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    uploaded_by: Optional[str] = None
    created_at: Optional[datetime] = None

class ResumeEvaluation(BaseModel):
    resume_id: str
    job_id: str

    # Scores
    relevance_score: float = Field(ge=0, le=100)
    hard_match_score: float = Field(ge=0, le=100)
    soft_match_score: float = Field(ge=0, le=100)

    # Analysis
    matched_skills: List[str] = []
    missing_skills: List[str] = []
    matched_experience: List[str] = []
    missing_requirements: List[str] = []

    # Verdict
    verdict: str = Field(pattern="^(HIGH|MEDIUM|LOW)$")

    # Feedback
    suggestions: List[str] = []
    strengths: List[str] = []
    improvements: List[str] = []

    # Metadata
    evaluated_at: Optional[datetime] = None
