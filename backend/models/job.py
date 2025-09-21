# backend/models/job.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class JobDescription(BaseModel):
    job_id: Optional[str] = Field(description="Unique job identifier")
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    location: Optional[str] = None

    # Requirements
    required_skills: List[str] = []
    optional_skills: List[str] = []
    min_experience: int = 0
    max_experience: Optional[int] = None
    education_requirements: List[str] = []
    certifications_required: List[str] = []
    projects_required: List[str] = [] # Added this line

    # Description
    raw_text: Optional[str] = ""
    processed_text: Optional[str] = ""
    responsibilities: List[str] = []

    # Embeddings
    embeddings: Optional[List[float]] = None

    # Metadata
    posted_by: Optional[str] = None
    created_at: Optional[datetime] = None
    deadline: Optional[datetime] = None
    status: str = Field(default="active", pattern="^(active|closed|paused)$")