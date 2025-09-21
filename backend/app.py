# backend/app.py
from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Header, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from fastapi import Form
import os
import tempfile
from datetime import datetime
import logging
import uuid
import json
import hashlib
import hmac
import secrets
from backend.services.parser import DocumentParser
from backend.services.embedding import EmbeddingService
from backend.services.scoring import ScoringEngine
from backend.config import Config
from backend.database.mongodb import MongoDB 

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Simple JSON file-backed storage (fallback to local storage so app runs without MongoDB)
class LocalStorage:
    def __init__(self, data_dir="data"):
        os.makedirs(data_dir, exist_ok=True)
        self.data_dir = data_dir
        self.resumes_path = os.path.join(data_dir, "resumes.json")
        self.jobs_path = os.path.join(data_dir, "jobs.json")
        self.evals_path = os.path.join(data_dir, "evaluations.json")
        self.recruiters_path = os.path.join(data_dir, "recruiters.json")
        self.apps_path = os.path.join(data_dir, "applications.json")
        self._ensure_files()

    def _ensure_files(self):
        for p in [self.resumes_path, self.jobs_path, self.evals_path,
                  self.recruiters_path, self.apps_path]:
            if not os.path.exists(p):
                with open(p, 'w', encoding='utf-8') as f:
                    json.dump([], f)

    def _load(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _save(self, path, data):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # resumes
    def insert_resume(self, resume_doc: dict) -> str:
        data = self._load(self.resumes_path)
        resume_id = str(uuid.uuid4())
        resume_doc['_id'] = resume_id
        resume_doc['created_at'] = datetime.utcnow().isoformat()
        data.append(resume_doc)
        self._save(self.resumes_path, data)
        return resume_id

    def get_resume_by_id(self, resume_id: str) -> Optional[dict]:
        data = self._load(self.resumes_path)
        for r in data:
            if r.get('_id') == resume_id:
                return r
        return None

    # jobs
    def insert_job_description(self, job_doc: dict) -> str:
        data = self._load(self.jobs_path)
        job_id = job_doc.get('job_id') or str(uuid.uuid4())
        job_doc['_id'] = job_id
        job_doc['created_at'] = datetime.utcnow().isoformat()
        data.append(job_doc)
        self._save(self.jobs_path, data)
        return job_id

    def get_job_by_id(self, job_id: str) -> Optional[dict]:
        data = self._load(self.jobs_path)
        for j in data:
            if j.get('_id') == job_id or j.get('job_id') == job_id:
                return j
        return None

    # evaluations
    def insert_evaluation(self, eval_doc: dict) -> str:
        data = self._load(self.evals_path)
        eval_id = str(uuid.uuid4())
        eval_doc['_id'] = eval_id
        eval_doc['evaluated_at'] = datetime.utcnow().isoformat()
        data.append(eval_doc)
        self._save(self.evals_path, data)
        return eval_id

    def get_evaluations_by_job(self, job_id: str, min_score: Optional[int] = None) -> List[dict]:
        data = self._load(self.evals_path)
        res = [e for e in data if e.get('job_id') == job_id]
        if min_score:
            res = [e for e in res if e.get('relevance_score', 0) >= min_score]
        return res

    # applications (student applies to a job)
    def insert_application(self, app_doc: dict) -> str:
        data = self._load(self.apps_path)
        app_id = str(uuid.uuid4())
        app_doc['_id'] = app_id
        app_doc['created_at'] = datetime.utcnow().isoformat()
        data.append(app_doc)
        self._save(self.apps_path, data)
        return app_id

    # recruiters (simple API-key based auth for demo)
    def insert_employee(self, emp_doc: dict) -> str:
        """
        Create an employee record for simple email/password login.
        Stores salted SHA256 password hash (demo only).
        Returns generated emp_api_key.
        """
        data = self._load(self.recruiters_path)  # reuse same file or create a new employees file if you want
        # You may want a separate file; for simplicity we use recruiters_path but mark type
        emp_id = str(uuid.uuid4())
        salt = secrets.token_hex(8)
        pw = emp_doc.get('password', '')
        pw_hash = hashlib.sha256((salt + pw).encode('utf-8')).hexdigest()
        emp_doc_record = {
            "_id": emp_id,
            "email": emp_doc.get("email"),
            "name": emp_doc.get("name"),
            "company": emp_doc.get("company"),
            "salt": salt,
            "password_hash": pw_hash,
            "emp_api_key": emp_doc.get("emp_api_key") or secrets.token_hex(24),
            "role": emp_doc.get("role", "employee"),
            "created_at": datetime.utcnow().isoformat()
        }
        # load existing employees (we'll store in the same recruiters file but with role employee)
        data = self._load(self.recruiters_path)
        data.append(emp_doc_record)
        self._save(self.recruiters_path, data)
        return emp_doc_record['emp_api_key']

    def get_employee_by_api_key(self, api_key: str) -> Optional[dict]:
        data = self._load(self.recruiters_path)
        for r in data:
            if r.get('emp_api_key') == api_key:
                return r
        return None

    def get_employee_by_credentials(self, email: str, password: str) -> Optional[dict]:
        data = self._load(self.recruiters_path)
        for r in data:
            if r.get('email') and r.get('email').lower() == email.lower() and r.get('password_hash') and r.get('salt'):
                salt = r.get('salt', '')
                calc = hashlib.sha256((salt + password).encode('utf-8')).hexdigest()
                # constant-time compare
                if hmac.compare_digest(calc, r.get('password_hash')):
                    return r
        return None

    def insert_recruiter(self, rec_doc: dict) -> str:
        data = self._load(self.recruiters_path)
        rec_id = str(uuid.uuid4())
        rec_doc['_id'] = rec_id
        rec_doc['api_key'] = rec_doc.get('api_key') or str(uuid.uuid4().hex)
        rec_doc['created_at'] = datetime.utcnow().isoformat()
        data.append(rec_doc)
        self._save(self.recruiters_path, data)
        return rec_doc['api_key']

    def get_recruiter_by_api_key(self, api_key: str) -> Optional[dict]:
        data = self._load(self.recruiters_path)
        for r in data:
            if r.get('api_key') == api_key:
                return r
        return None

    @property
    def db(self):
        # mimic pymongo-like access for app.get_all_jobs
        return {
            Config.JOBS_COLLECTION: self._load(self.jobs_path),
            Config.RESUMES_COLLECTION: self._load(self.resumes_path)
        }


# Initialize FastAPI app
app = FastAPI(
    title="Resume Relevance Check System",
    description="AI-powered resume evaluation system (local demo)",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
parser = DocumentParser()
embedding_service = EmbeddingService()
scoring_engine = ScoringEngine()
mongodb = LocalStorage()


@app.get("/")
async def root():
    return {"status": "active", "message": "Resume Relevance Check System is running (local mode)"}


# Recruiter register (returns API key)

@app.post("/api/employee/create")
async def create_employee(email: str = Body(...), password: str = Body(...), name: str = Body(...), company: str = Body(None)):
    """
    Create an employee credential. Use Postman to call this (no UI).
    Returns emp_api_key to be used as X-EMP-KEY in requests.
    """
    try:
        emp_doc = {
            "email": email,
            "password": password,
            "name": name,
            "company": company
        }
        emp_api_key = mongodb.insert_employee(emp_doc)
        return {"status": "success", "emp_api_key": emp_api_key}
    except Exception as e:
        logger.error(f"Error creating employee: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/employee/login")
async def employee_login(email: str = Body(...), password: str = Body(...)):
    """
    Employee login that returns emp_api_key. Frontend will call this with email/password.
    """
    try:
        emp = mongodb.get_employee_by_credentials(email, password)
        if not emp:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return {
            "status": "success",
            "emp_api_key": emp.get("emp_api_key"),
            "employee": {"email": emp.get("email"), "name": emp.get("name"), "company": emp.get("company")}
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error on employee login: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/api/recruiter/register")
async def register_recruiter(email: str = Query(...), name: str = Query(...), company: str = Query(...)):
    rec = {
        "email": email,
        "name": name,
        "company": company,
    }
    api_key = mongodb.insert_recruiter(rec)
    return {"status": "success", "api_key": api_key, "message": "Recruiter created. Use X-API-Key header for protected endpoints."}


# Student apply -> upload resume
@app.post("/api/apply")
async def apply_for_job(
    job_id: str = Query(...),
    file: UploadFile = File(...),
    candidate_email: str = Query(...),
    candidate_name: Optional[str] = None
):
    try:
        job_desc = mongodb.get_job_by_id(job_id)
        if not job_desc:
            raise HTTPException(status_code=404, detail="Job description not found")

        if not file.filename.endswith(('.pdf', '.docx', '.doc')):
            raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")

        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        file_type = 'pdf' if file.filename.endswith('.pdf') else 'docx'
        parsed_data = parser.parse_resume(tmp_path, file_type)
        parsed_data['candidate_email'] = candidate_email
        if candidate_name:
            parsed_data['candidate_name'] = candidate_name
        parsed_data['file_name'] = file.filename
        parsed_data['file_type'] = file_type

        embeddings = embedding_service.generate_embeddings(parsed_data['processed_text'])
        parsed_data['embeddings'] = embeddings

        resume_id = mongodb.insert_resume(parsed_data)
        embedding_service.store_resume_embedding(
            resume_id,
            parsed_data['processed_text'],
            {'candidate_name': parsed_data['candidate_name'], 'email': candidate_email}
        )

        # create application record
        app_doc = {
            "job_id": job_id,
            "resume_id": resume_id,
            "candidate_email": candidate_email,
            "candidate_name": parsed_data.get('candidate_name'),
            "status": "applied"
        }
        mongodb.insert_application(app_doc)

        try:
            os.unlink(tmp_path)
        except:
            pass

        return {
            "status": "success",
            "resume_id": resume_id,
            "message": "Resume uploaded successfully."
        }

    except Exception as e:
        logger.error(f"Error in apply_for_job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bulk-upload-resumes")
async def bulk_upload_resumes(
    job_id: str = Query(...),
    files: List[UploadFile] = File(...)
):
    job_desc = mongodb.get_job_by_id(job_id)
    if not job_desc:
        raise HTTPException(status_code=404, detail="Job description not found")

    successful_uploads = []
    failed_uploads = []

    for file in files:
        try:
            if not file.filename.endswith(('.pdf', '.docx', '.doc')):
                failed_uploads.append({"filename": file.filename, "error": "Unsupported file type"})
                continue

            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
                content = await file.read()
                tmp.write(content)
                tmp_path = tmp.name

            file_type = 'pdf' if file.filename.endswith('.pdf') else 'docx'
            parsed_data = parser.parse_resume(tmp_path, file_type)
            # For bulk uploads, we may not have candidate name/email, so we can leave them blank
            parsed_data['candidate_email'] = parsed_data.get('candidate_email') or "N/A"
            parsed_data['candidate_name'] = parsed_data.get('candidate_name') or "Unknown"
            parsed_data['file_name'] = file.filename
            parsed_data['file_type'] = file_type

            embeddings = embedding_service.generate_embeddings(parsed_data['processed_text'])
            parsed_data['embeddings'] = embeddings

            resume_id = mongodb.insert_resume(parsed_data)
            embedding_service.store_resume_embedding(
                resume_id,
                parsed_data['processed_text'],
                {'candidate_name': parsed_data['candidate_name'], 'email': parsed_data['candidate_email']}
            )

            # create application record
            app_doc = {
                "job_id": job_id,
                "resume_id": resume_id,
                "candidate_email": parsed_data.get('candidate_email'),
                "candidate_name": parsed_data.get('candidate_name'),
                "status": "applied"
            }
            mongodb.insert_application(app_doc)
            successful_uploads.append(resume_id)

            try:
                os.unlink(tmp_path)
            except:
                pass
        except Exception as e:
            logger.error(f"Failed to process file {file.filename}: {e}")
            failed_uploads.append({"filename": file.filename, "error": str(e)})

    return {
        "status": "completed",
        "successful_uploads": len(successful_uploads),
        "failed_uploads": len(failed_uploads),
        "details": failed_uploads
    }


# Upload job (recruiter-protected now)
@app.post("/api/upload-job")
async def upload_job_description(
    file: Optional[UploadFile] = File(None),
    job_text_json: Optional[str] = Body(None),      # JSON body
    job_text_form: Optional[str] = Form(None),      # form field
    job_text_q: Optional[str] = Query(None),        # query fallback (optional)
    job_title: str = Query(...),
    company_name: str = Query(...),
    location: str = Query(...),
    posted_by: str = Query(...)
):
    try:
        # Collect job_text from any supported source
        job_text = None
        if file:
            content = await file.read()
            job_text = content.decode("utf-8")
        else:
            job_text = job_text_json or job_text_form or job_text_q

        if not job_text:
            raise HTTPException(status_code=400, detail="Either file or job_text must be provided")

        parsed_job = parser.parse_job_description(job_text)
        parsed_job['job_title'] = job_title
        parsed_job['company_name'] = company_name
        parsed_job['location'] = location
        parsed_job['posted_by'] = posted_by
        parsed_job['job_id'] = f"{company_name}_{job_title}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        embeddings = embedding_service.generate_embeddings(parsed_job['processed_text'])
        parsed_job['embeddings'] = embeddings

        job_id = mongodb.insert_job_description(parsed_job)
        embedding_service.store_job_embedding(
            job_id,
            parsed_job['processed_text'],
            {'job_title': job_title, 'company': company_name}
        )

        return {
            "status": "success",
            "job_id": job_id,
            "job_title": job_title,
            "required_skills": parsed_job.get('required_skills', []),
            "message": "Job description uploaded successfully"
        }
    except HTTPException as e:
        # Preserve intended HTTP status (e.g., 400)
        raise e
    except Exception as e:
        logger.error(f"Error uploading job description: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# (existing) evaluate single resume
@app.post("/api/evaluate-resume")
async def evaluate_single_resume(
    resume_id: str = Query(...),
    job_id: str = Query(...)
):
    try:
        resume = mongodb.get_resume_by_id(resume_id)
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")

        job_desc = mongodb.get_job_by_id(job_id)
        if not job_desc:
            raise HTTPException(status_code=404, detail="Job description not found")

        evaluation = scoring_engine.evaluate_resume(resume, job_desc)
        eval_id = mongodb.insert_evaluation(evaluation)
        evaluation['evaluation_id'] = eval_id

        return {
            "status": "success",
            "evaluation": evaluation,
            "message": "Resume evaluated successfully"
        }

    except Exception as e:
        logger.error(f"Error evaluating resume: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# (existing) evaluate-batch protected
@app.post("/api/evaluate-batch")
async def evaluate_batch_resumes(
    job_id: str = Query(...),
    resume_ids: Optional[List[str]] = None
):
    try:
        job_desc = mongodb.get_job_by_id(job_id)
        if not job_desc:
            raise HTTPException(status_code=404, detail="Job description not found")

        if resume_ids:
            resumes = [mongodb.get_resume_by_id(rid) for rid in resume_ids]
            resumes = [r for r in resumes if r is not None]
        else:
            similar_resumes = embedding_service.find_similar_resumes(job_desc['embeddings'], top_k=50)
            resumes = [mongodb.get_resume_by_id(r['resume_id']) for r in similar_resumes]
            resumes = [r for r in resumes if r is not None]

        if not resumes:
            raise HTTPException(status_code=404, detail="No resumes found for evaluation")

        evaluations = scoring_engine.batch_evaluate(resumes, job_desc)
        for evaluation in evaluations:
            eval_id = mongodb.insert_evaluation(evaluation)
            evaluation['evaluation_id'] = eval_id

        return {
            "status": "success",
            "total_evaluated": len(evaluations),
            "evaluations": evaluations[:20],
            "summary": {
                "high_matches": len([e for e in evaluations if e['verdict'] == 'HIGH']),
                "medium_matches": len([e for e in evaluations if e['verdict'] == 'MEDIUM']),
                "low_matches": len([e for e in evaluations if e['verdict'] == 'LOW'])
            }
        }

    except Exception as e:
        logger.error(f"Error in batch evaluation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/job-evaluations/{job_id}")
async def get_job_evaluations(
    job_id: str,
    min_score: Optional[int] = None,
    verdict: Optional[str] = None
):
    try:
        evaluations = mongodb.get_evaluations_by_job(job_id, min_score)
        if verdict:
            evaluations = [e for e in evaluations if e.get('verdict') == verdict.upper()]
        return {
            "status": "success",
            "job_id": job_id,
            "total_evaluations": len(evaluations),
            "evaluations": evaluations
        }
    except Exception as e:
        logger.error(f"Error fetching evaluations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload-resume")
async def upload_resume(
    file: UploadFile = File(...),
    candidate_email: str = Query(...),
    candidate_name: Optional[str] = None
):
    try:
        if not file.filename.endswith(('.pdf', '.docx', '.doc')):
            raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")

        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        file_type = 'pdf' if file.filename.endswith('.pdf') else 'docx'
        parsed_data = parser.parse_resume(tmp_path, file_type)
        parsed_data['candidate_email'] = candidate_email
        if candidate_name:
            parsed_data['candidate_name'] = candidate_name
        parsed_data['file_name'] = file.filename
        parsed_data['file_type'] = file_type

        embeddings = embedding_service.generate_embeddings(parsed_data['processed_text'])
        parsed_data['embeddings'] = embeddings

        resume_id = mongodb.insert_resume(parsed_data)
        embedding_service.store_resume_embedding(
            resume_id,
            parsed_data['processed_text'],
            {'candidate_name': parsed_data.get('candidate_name', ''), 'email': candidate_email}
        )

        try:
            os.unlink(tmp_path)
        except:
            pass

        return {
            "status": "success",
            "resume_id": resume_id,
            "skills_extracted": len(parsed_data.get('skills', [])),
            "message": "Resume uploaded successfully"
        }

    except Exception as e:
        logger.error(f"Error in upload_resume: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jobs")
async def get_all_jobs(
    status: Optional[str] = "active",
    limit: int = 20
):
    try:
        jobs = mongodb.db.get(Config.JOBS_COLLECTION, [])[:limit]
        return {
            "status": "success",
            "total_jobs": len(jobs),
            "jobs": jobs
        }
    except Exception as e:
        logger.error(f"Error fetching jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/resumes")
async def get_all_resumes(
    limit: int = 10
):
    try:
        resumes = mongodb.db.get(Config.RESUMES_COLLECTION, [])[:limit]
        return {
            "status": "success",
            "total_resumes": len(resumes),
            "resumes": resumes
        }
    except Exception as e:
        logger.error(f"Error fetching resumes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)