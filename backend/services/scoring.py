# backend/services/scoring.py
from typing import Dict, List, Any
from backend.config import Config
from backend.services.matching import MatchingService
from backend.services.embedding import EmbeddingService
import logging
import re

logger = logging.getLogger(__name__)

class ScoringEngine:
    def __init__(self):
        self.matching_service = MatchingService()
        self.embedding_service = EmbeddingService()

        # Note: LLM feedback chain left unchanged from your original implementation (optional)
        self.llm = None
        self.feedback_chain = None

    def evaluate_resume(self, resume: Dict, job_desc: Dict) -> Dict[str, Any]:
        """Complete evaluation of resume against job description."""
        # 1. Calculate hard match scores (keyword-based)
        hard_match_results = self.matching_service.calculate_hard_match(resume, job_desc)

        # 2. Calculate soft match score using embeddings
        resume_embedding = resume.get('embeddings') or self.embedding_service.generate_embeddings(resume.get('processed_text', ''))
        job_embedding = job_desc.get('embeddings') or self.embedding_service.generate_embeddings(job_desc.get('processed_text', ''))

        soft_score = self.embedding_service.calculate_similarity(resume_embedding, job_embedding)  # already in 0-100

        # 3. Combine using weights
        hard_score = hard_match_results.get('overall_hard_match', 0.0)
        w_hard = Config.HARD_MATCH_WEIGHT
        w_soft = Config.SOFT_MATCH_WEIGHT

        relevance_score = (hard_score * w_hard) + (soft_score * w_soft)

        # clamp
        if relevance_score > 100:
            relevance_score = 100.0
        if relevance_score < 0:
            relevance_score = 0.0

        evaluation = {
            'resume_id': str(resume.get('_id', '')),
            'job_id': str(job_desc.get('_id', '')),
            'relevance_score': round(relevance_score, 2),
            'hard_match_score': round(hard_score, 2),
            'soft_match_score': round(soft_score, 2),
            'analysis': {
                'matched_skills': hard_match_results.get('matched_skills', []),
                'missing_skills': hard_match_results.get('missing_skills', []),
                'experience_details': hard_match_results.get('details', {})
            },
            'verdict': '',
            'feedback': {}
        }

        # 5. Determine verdict
        if relevance_score >= Config.HIGH_THRESHOLD:
            evaluation['verdict'] = 'HIGH'
        elif relevance_score >= Config.MEDIUM_THRESHOLD:
            evaluation['verdict'] = 'MEDIUM'
        else:
            evaluation['verdict'] = 'LOW'

        # 6. (Optional) generate feedback using LLM if configured -- left minimal here
        evaluation['feedback'] = self.generate_feedback(resume, job_desc, evaluation)

        return evaluation

    def generate_feedback(self, resume: Dict, job_desc: Dict, evaluation: Dict) -> Dict[str, List[str]]:
        feedback = {
            'strengths': [],
            'improvements': [],
            'suggestions': []
        }

        if evaluation['analysis'].get('matched_skills'):
            feedback['strengths'].append(
                f"Matched skills: {', '.join(evaluation['analysis']['matched_skills'][:6])}"
            )

        if evaluation['analysis'].get('missing_skills'):
            feedback['improvements'].append(
                f"Missing key skills: {', '.join(evaluation['analysis']['missing_skills'][:6])}"
            )
            feedback['suggestions'].append("Consider projects or a micro-course to demonstrate these skills.")

        # Note: if you have LLM access you can generate nicer suggestions here.
        return feedback

    def batch_evaluate(self, resumes: List[Dict], job_desc: Dict) -> List[Dict]:
        """Evaluate multiple resumes."""
        evaluations = []
        for resume in resumes:
            evaluations.append(self.evaluate_resume(resume, job_desc))
        evaluations.sort(key=lambda x: x['relevance_score'], reverse=True)
        return evaluations