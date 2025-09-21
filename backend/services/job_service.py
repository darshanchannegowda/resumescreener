# backend/services/job_service.py
import os
import json
import uuid
import tempfile
import logging
from datetime import datetime
from typing import Optional

import google.generativeai as genai
from fastapi import UploadFile

from backend.models.job import JobDescription
from backend.services.embedding import EmbeddingService
from backend.config import Config

# local parser (your parser.py)
from backend.services import parser as doc_parser_module  # ensure backend/services/__init__ imports parser or adjust import

logger = logging.getLogger(__name__)
os.makedirs(Config.DATA_DIR, exist_ok=True)

JOB_DB_PATH = os.path.join(Config.DATA_DIR, "jobs_db.json")

# configure genai if key present
if Config.GEMINI_API_KEY:
    try:
        genai.configure(api_key=Config.GEMINI_API_KEY)
    except Exception as e:
        logger.warning(f"Failed configure Gemini: {e}")


class JobService:
    def __init__(self):
        self.parser = doc_parser_module.DocumentParser()
        self.embedding_service = EmbeddingService()

        # load existing jobs
        if os.path.exists(JOB_DB_PATH):
            try:
                with open(JOB_DB_PATH, "r", encoding="utf-8") as f:
                    self._jobs = json.load(f)
            except Exception:
                self._jobs = {}
        else:
            self._jobs = {}

    async def upload_job_description(self, job_title: str, company_name: str, location: str, posted_by: str, file: Optional[UploadFile], job_text: Optional[str]):
        """
        Accepts either an uploaded file (pdf/docx) or raw job_text.
        Parses with Gemini (if configured) and falls back to local parser.
        Stores the job JSON and creates & persists an embedding.
        """
        try:
            # Step 1: get raw text
            raw_text = job_text or ""
            temp_path = None
            if file:
                suffix = os.path.splitext(file.filename)[1].lower()
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(await file.read())
                    temp_path = tmp.name
                # use parser methods
                if suffix == ".pdf":
                    raw_text = self.parser.extract_text_from_pdf(temp_path)
                else:
                    raw_text = self.parser.extract_text_from_docx(temp_path)

                # remove temp
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass

            if not raw_text:
                return {"status": "error", "message": "No text extracted from file or job_text empty."}

            # Step 2: try Gemini structured parsing
            parsed = None
            if Config.GEMINI_API_KEY:
                try:
                    model = genai.GenerativeModel(Config.GEMINI_MODEL or "gemini-1.5-flash")
                    prompt = self._build_prompt_for_gemini(raw_text)
                    resp = model.generate_content(prompt)
                    json_text = resp.text.strip()
                    # strip code fences if present
                    if json_text.startswith("```"):
                        json_text = json_text.split("```", 2)[-1]
                    parsed = json.loads(json_text)
                except Exception as e:
                    logger.warning(f"Gemini parse failed: {e}. Falling back to local parser.")
                    parsed = None

            # Step 3: fallback local parser if Gemini didn't return valid data
            if not parsed:
                parsed = self.parser.parse_job_description(raw_text)

            # Normalize fields into JobDescription
            job_id = str(uuid.uuid4())
            jd = JobDescription(
                job_id=job_id,
                company_name=company_name or parsed.get("company_name", ""),
                job_title=job_title or parsed.get("job_title", ""),
                location=location or parsed.get("location", ""),
                required_skills=parsed.get("required_skills", []),
                optional_skills=parsed.get("optional_skills", []),
                min_experience=parsed.get("min_experience", 0),
                education_requirements=parsed.get("education_requirements", []),
                certifications_required=parsed.get("certifications_required", []),
                projects_required=parsed.get("projects_required", []),
                raw_text=parsed.get("raw_text", raw_text),
                processed_text=parsed.get("processed_text", self.parser.preprocess_text(raw_text)),
                responsibilities=parsed.get("responsibilities", []),
                posted_by=posted_by,
                created_at=datetime.utcnow().isoformat()
            )

            # Step 4: create & store embedding
            try:
                emb = self.embedding_service.store_job_embedding(job_id, jd.processed_text, metadata={
                    "job_title": jd.job_title, "company_name": jd.company_name
                })
                # store embedding vector in job record as well (optional)
                jd.embeddings = emb
            except Exception as e:
                logger.error(f"Embedding store failed: {e}")

            # Step 5: persist job to local DB
            self._jobs[job_id] = json.loads(jd.json())
            with open(JOB_DB_PATH, "w", encoding="utf-8") as f:
                json.dump(self._jobs, f, ensure_ascii=False, indent=2)

            return {"status": "ok", "job_id": job_id, "job": self._jobs[job_id]}

        except Exception as e:
            logger.exception("Failed uploading job")
            return {"status": "error", "message": str(e)}

    def get_all_jobs(self, status: str = "active", limit: int = 20):
        jobs_list = list(self._jobs.values())[:limit]
        return {"count": len(jobs_list), "jobs": jobs_list}

    def _build_prompt_for_gemini(self, raw_text: str) -> str:
        prompt = f"""
        Extract a JSON object from the following job description. The JSON must include keys:
        job_title (string), company_name (string), location (string),
        raw_text (string), processed_text (string), required_skills (array),
        optional_skills (array), min_experience (int), education_requirements (array),
        certifications_required (array), responsibilities (array), projects_required (array).

        Use empty string "" or empty array [] where data is missing. Return ONLY valid JSON.

        Job Description:
        {raw_text}
        """
        return prompt
