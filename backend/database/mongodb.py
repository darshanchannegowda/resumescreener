# backend/database/mongodb.py

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from typing import Optional, Dict, List, Any
from datetime import datetime
from backend.config import Config
import logging
import hashlib
import hmac
import secrets
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MongoDB:
    def __init__(self):
        self.client = None
        self.db = None
        self.connect()
    
    def connect(self):
        """Establish connection to MongoDB Atlas"""
        try:
            self.client = MongoClient(Config.MONGODB_URI)
            self.db = self.client[Config.DATABASE_NAME]
            
            # Test connection
            self.client.admin.command('ping')
            logger.info("Successfully connected to MongoDB Atlas")
            
            # Create indexes for better performance
            self._create_indexes()
            
        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    def _create_indexes(self):
        """Create necessary indexes for optimal query performance"""
        # Resume indexes
        self.db[Config.RESUMES_COLLECTION].create_index([("candidate_email", 1)])
        self.db[Config.RESUMES_COLLECTION].create_index([("created_at", -1)])
        
        # Job description indexes
        self.db[Config.JOBS_COLLECTION].create_index([("job_id", 1)], unique=True)
        self.db[Config.JOBS_COLLECTION].create_index([("created_at", -1)])
        
        # Evaluation indexes
        self.db[Config.EVALUATIONS_COLLECTION].create_index([
            ("resume_id", 1), 
            ("job_id", 1)
        ])
        self.db[Config.EVALUATIONS_COLLECTION].create_index([("relevance_score", -1)])
        self.db[Config.EVALUATIONS_COLLECTION].create_index([("verdict", 1)])

        # Recruiters/Employees indexes
        self.db["recruiters"].create_index([("email", 1)], unique=True)
        self.db["recruiters"].create_index([("api_key", 1)])
        self.db["recruiters"].create_index([("emp_api_key", 1)])

    def insert_resume(self, resume_data: Dict) -> str:
        """Insert a resume into the database"""
        resume_data['created_at'] = datetime.utcnow()
        resume_data['updated_at'] = datetime.utcnow()
        result = self.db[Config.RESUMES_COLLECTION].insert_one(resume_data)
        return str(result.inserted_id)
    
    def insert_job_description(self, job_data: Dict) -> str:
        """Insert a job description into the database"""
        job_data['created_at'] = datetime.utcnow()
        job_data['updated_at'] = datetime.utcnow()
        result = self.db[Config.JOBS_COLLECTION].insert_one(job_data)
        return str(result.inserted_id)
    
    def insert_evaluation(self, evaluation_data: Dict) -> str:
        """Insert an evaluation result"""
        evaluation_data['created_at'] = datetime.utcnow()
        result = self.db[Config.EVALUATIONS_COLLECTION].insert_one(evaluation_data)
        return str(result.inserted_id)
    
    def get_evaluations_by_job(self, job_id: str, min_score: Optional[int] = None) -> List[Dict]:
        """Get all evaluations for a specific job"""
        query = {"job_id": job_id}
        if min_score:
            query["relevance_score"] = {"$gte": min_score}
        
        return list(self.db[Config.EVALUATIONS_COLLECTION].find(
            query
        ).sort("relevance_score", -1))
    
    def get_resume_by_id(self, resume_id: str) -> Optional[Dict]:
        """Get resume by ID"""
        from bson import ObjectId
        return self.db[Config.RESUMES_COLLECTION].find_one({"_id": ObjectId(resume_id)})
    
    def get_job_by_id(self, job_id: str) -> Optional[Dict]:
        """Get job description by ID"""
        from bson import ObjectId
        return self.db[Config.JOBS_COLLECTION].find_one({"_id": ObjectId(job_id)})

    def insert_employee(self, emp_doc: dict) -> str:
        """
        Create an employee record for simple email/password login.
        Stores salted SHA256 password hash.
        Returns generated emp_api_key.
        """
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
        self.db["recruiters"].insert_one(emp_doc_record)
        return emp_doc_record['emp_api_key']

    def get_employee_by_credentials(self, email: str, password: str) -> Optional[dict]:
        user = self.db["recruiters"].find_one({"email": email.lower()})
        if user and user.get('password_hash') and user.get('salt'):
            salt = user.get('salt', '')
            calc = hashlib.sha256((salt + password).encode('utf-8')).hexdigest()
            if hmac.compare_digest(calc, user.get('password_hash')):
                return user
        return None

    def insert_recruiter(self, rec_doc: dict) -> str:
        rec_id = str(uuid.uuid4())
        rec_doc['_id'] = rec_id
        rec_doc['api_key'] = rec_doc.get('api_key') or str(uuid.uuid4().hex)
        rec_doc['created_at'] = datetime.utcnow().isoformat()
        self.db["recruiters"].insert_one(rec_doc)
        return rec_doc['api_key']

    def get_recruiter_by_api_key(self, api_key: str) -> Optional[dict]:
        return self.db["recruiters"].find_one({"api_key": api_key})