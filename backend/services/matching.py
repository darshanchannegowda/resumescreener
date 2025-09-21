from typing import Dict, List, Tuple, Any
from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import re
from backend.config import Config
import logging

logger = logging.getLogger(__name__)

class MatchingService:
    def __init__(self):
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=2000,
            stop_words='english',
            ngram_range=(1, 2)
        )

    def calculate_hard_match(self, resume: Dict, job_desc: Dict) -> Dict[str, Any]:
        """Calculate hard match score based on keywords and requirements"""
        scores = {
            'skills_match': 0,
            'education_match': 0,
            'experience_match': 0,
            'certification_match': 0,
            'matched_skills': [],
            'missing_skills': [],
            'matched_certifications': [],
            'missing_certifications': [],
            'details': {}
        }

        # 1. Skills matching
        resume_skills = [s.lower() for s in resume.get('skills', [])]
        required_skills = [s.lower() for s in job_desc.get('required_skills', [])]
        optional_skills = [s.lower() for s in job_desc.get('optional_skills', [])]

        matched_required = []
        missing_required = []

        for skill in required_skills:
            if self._fuzzy_skill_match(skill, resume_skills):
                matched_required.append(skill)
            else:
                missing_required.append(skill)

        matched_optional = []
        for skill in optional_skills:
            if self._fuzzy_skill_match(skill, resume_skills):
                matched_optional.append(skill)

        if required_skills:
            required_score = (len(matched_required) / len(required_skills)) * 70
        else:
            required_score = 70

        if optional_skills:
            optional_score = (len(matched_optional) / len(optional_skills)) * 30
        else:
            optional_score = 30

        scores['skills_match'] = required_score + optional_score
        scores['matched_skills'] = matched_required + matched_optional
        scores['missing_skills'] = missing_required

        # 2. Experience matching
        min_exp = job_desc.get('min_experience', 0)
        max_exp = job_desc.get('max_experience', min_exp + 10 if min_exp >= 0 else 10)

        resume_exp = self._extract_experience_years(resume.get('raw_text', ''))

        if resume_exp >= min_exp:
            if resume_exp <= max_exp:
                scores['experience_match'] = 100
            else:
                scores['experience_match'] = 80
        else:
            if min_exp > 0:
                scores['experience_match'] = (resume_exp / min_exp) * 100
            else:
                scores['experience_match'] = 100

        scores['details']['resume_experience'] = resume_exp
        scores['details']['required_experience'] = f"{min_exp}-{max_exp} years"

        # 3. Education matching
        job_education = job_desc.get('education_requirements', [])
        resume_education = resume.get('education', [])

        if job_education and resume_education:
            education_match = self._match_education(resume_education, job_education)
            scores['education_match'] = education_match * 100
        else:
            scores['education_match'] = 100

        # 4. Certification matching
        resume_certs = [c.lower() for c in resume.get('certifications', [])]
        required_certs = [c.lower() for c in job_desc.get('certifications_required', [])]
        
        matched_certs = []
        missing_certs = []

        for cert in required_certs:
            if self._fuzzy_skill_match(cert, resume_certs, threshold=70):
                matched_certs.append(cert)
            else:
                missing_certs.append(cert)

        if required_certs:
            scores['certification_match'] = (len(matched_certs) / len(required_certs)) * 100
        else:
            scores['certification_match'] = 100

        scores['matched_certifications'] = matched_certs
        scores['missing_certifications'] = missing_certs

        # 5. Overall hard match using weights
        weights = {
            'skills': 0.5,
            'experience': 0.3,
            'education': 0.15,
            'certifications': 0.05
        }

        overall_score = (
            scores['skills_match'] * weights['skills'] +
            scores['experience_match'] * weights['experience'] +
            scores['education_match'] * weights['education'] +
            scores['certification_match'] * weights['certifications']
        )

        scores['overall_hard_match'] = overall_score

        return scores

    def calculate_soft_match(self, resume_text: str, job_text: str,
                             resume_embedding: List[float],
                             job_embedding: List[float]) -> Dict[str, Any]:
        """Calculate soft match using semantic similarity"""
        scores = {
            'tfidf_similarity': 0,
            'embedding_similarity': 0,
            'keyword_density': 0,
            'overall_soft_match': 0
        }

        # 1. TF-IDF similarity
        try:
            tfidf_matrix = self.tfidf_vectorizer.fit_transform([resume_text, job_text])
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            scores['tfidf_similarity'] = similarity * 100
        except Exception as e:
            logger.error(f"TF-IDF calculation error: {e}")
            scores['tfidf_similarity'] = 0

        # 2. Embedding similarity (semantic)
        if resume_embedding is not None and job_embedding is not None:
            embedding_sim = self._cosine_similarity(resume_embedding, job_embedding)
            scores['embedding_similarity'] = embedding_sim * 100

        # 3. Keyword density
        job_keywords = self._extract_keywords(job_text)
        keyword_matches = sum(1 for keyword in job_keywords if keyword in resume_text.lower())
        if job_keywords:
            scores['keyword_density'] = (keyword_matches / len(job_keywords)) * 100

        # 4. Overall soft match (weighted)
        weights = {
            'tfidf': 0.3,
            'embedding': 0.5,
            'keywords': 0.2
        }

        scores['overall_soft_match'] = (
            scores['tfidf_similarity'] * weights['tfidf'] +
            scores['embedding_similarity'] * weights['embedding'] +
            scores['keyword_density'] * weights['keywords']
        )

        return scores

    def _fuzzy_skill_match(self, skill: str, resume_skills: List[str], threshold: int = 80) -> bool:
        """Check if skill matches any resume skill using fuzzy matching"""
        for resume_skill in resume_skills:
            if fuzz.ratio(skill, resume_skill) >= threshold:
                return True
            if fuzz.partial_ratio(skill, resume_skill) >= threshold:
                return True
        return False

    def _extract_experience_years(self, text: str) -> int:
        patterns = [
            r'(\d+)[\+\s]*years?\s+(?:of\s+)?experience',
            r'experience[:\s]+(\d+)[\+\s]*years?',
            r'(\d+)[\+\s]*years?\s+working'
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))

        year_mentions = re.findall(r'20\d{2}', text)
        if len(year_mentions) >= 2:
            years = sorted([int(y) for y in year_mentions])
            return years[-1] - years[0]
        return 0

    def _match_education(self, resume_education: List[Dict], job_requirements: List[str]) -> float:
        if not job_requirements:
            return 1.0

        resume_degrees = []
        for edu in resume_education:
            if isinstance(edu, dict):
                resume_degrees.append(edu.get('degree', '').lower())
                resume_degrees.append(edu.get('context', '').lower())

        resume_text = ' '.join(resume_degrees)

        matches = 0
        for requirement in job_requirements:
            if requirement.lower() in resume_text:
                matches += 1

        return matches / len(job_requirements) if job_requirements else 1.0

    def _extract_keywords(self, text: str, top_n: int = 20) -> List[str]:
        stop_words = {'the', 'is', 'at', 'which', 'on', 'and', 'a', 'an', 'as', 'are',
                      'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do',
                      'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might'}

        words = text.lower().split()
        keywords = []
        for word in words:
            word = re.sub(r'[^\w\s]', '', word)
            if len(word) > 3 and word not in stop_words:
                keywords.append(word)

        return list(dict.fromkeys(keywords))[:top_n]

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(dot_product / (norm1 * norm2))