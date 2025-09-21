import PyPDF2
import pdfplumber
import docx2txt
from typing import Dict, List, Any, Optional
import re
import spacy
import nltk
import logging

# Download required NLTK data (silent)
nltk.download('punkt', quiet=True)

# Load spaCy model (try to auto-download if missing)
try:
    nlp = spacy.load("en_core_web_sm")
except Exception:
    import subprocess
    subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"], check=False)
    nlp = spacy.load("en_core_web_sm")

logger = logging.getLogger(__name__)

class DocumentParser:
    def __init__(self):
        self.nlp = nlp

    def extract_text_from_pdf(self, file_path: str) -> str:
        text = ""
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            logger.warning(f"pdfplumber failed, trying PyPDF2 fallback: {e}")
            try:
                with open(file_path, 'rb') as file:
                    reader = PyPDF2.PdfReader(file)
                    for page in reader.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
            except Exception as e2:
                logger.error(f"PDF extraction failed: {e2}")
                raise
        return text.strip()

    def extract_text_from_docx(self, file_path: str) -> str:
        try:
            text = docx2txt.process(file_path)
            return text.strip()
        except Exception as e:
            logger.error(f"DOCX extraction failed: {e}")
            raise

    def extract_contact_info(self, text: str) -> Dict[str, Optional[str]]:
        contact = {
            'email': None,
            'phone': None,
            'name': None,
            'location': None
        }
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_match = re.search(email_pattern, text)
        if email_match:
            contact['email'] = email_match.group()

        phone_pattern = r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}'
        phone_match = re.search(phone_pattern, text)
        if phone_match:
            contact['phone'] = phone_match.group().strip()

        lines = [l.strip() for l in text.split('\n') if l.strip()]
        for line in lines[:8]:
            if len(line.split()) <= 4 and not any(char.isdigit() for char in line) and '@' not in line:
                contact['name'] = line
                break

        return contact

    def extract_skills(self, text: str) -> List[str]:
        skills = []
        tech_skills = [
            'Python', 'Java', 'JavaScript', 'C++', 'C#', 'SQL', 'NoSQL',
            'React', 'Angular', 'Vue', 'Node.js', 'Django', 'Flask', 'FastAPI',
            'MongoDB', 'PostgreSQL', 'MySQL', 'Redis', 'Docker', 'Kubernetes',
            'AWS', 'Azure', 'GCP', 'Machine Learning', 'Deep Learning',
            'NLP', 'Computer Vision', 'TensorFlow', 'PyTorch', 'Scikit-learn',
            'Git', 'CI/CD', 'Agile', 'Scrum', 'REST API', 'GraphQL'
        ]
        text_lower = text.lower()
        for skill in tech_skills:
            if skill.lower() in text_lower:
                skills.append(skill)

        skills_section_match = re.search(
            r'(?i)(skills|technical skills|competencies)[:\s]*([^\n]+(?:\n[^\n]+)*)',
            text
        )
        if skills_section_match:
            skills_text = skills_section_match.group(2)
            additional_skills = re.split(r'[,;|•\n]', skills_text)
            for skill in additional_skills:
                skill = skill.strip()
                if skill and len(skill) < 60:
                    skills.append(skill)

        seen = set()
        unique_skills = []
        for skill in skills:
            if skill and skill.lower() not in seen:
                seen.add(skill.lower())
                unique_skills.append(skill)
        return unique_skills

    def extract_education(self, text: str) -> List[Dict[str, str]]:
        education = []
        education_match = re.search(
            r'(?i)(education|academic|qualification)[:\s]*([^\n]+(?:\n[^\n]+)*)',
            text,
            re.MULTILINE
        )
        if education_match:
            edu_text = education_match.group(2)
            degree_patterns = [
                r'(B\.?Tech|B\.?E\.?|Bachelor)',
                r'(M\.?Tech|M\.?E\.?|M\.?S\.?|Master)',
                r'(PhD|Ph\.?D\.?|Doctorate)',
                r'(Diploma|Certificate)'
            ]
            for pattern in degree_patterns:
                matches = re.finditer(pattern, edu_text, re.IGNORECASE)
                for match in matches:
                    start = max(0, match.start() - 50)
                    end = min(len(edu_text), match.end() + 100)
                    context = edu_text[start:end]
                    education.append({
                        'degree': match.group(),
                        'context': context.strip()
                    })
        return education

    def extract_certifications(self, text: str) -> List[str]:
        certifications = []
        cert_section_match = re.search(
            r'(?i)(certifications|licenses|courses)[:\s]*([^\n]+(?:\n[^\n]+)*)',
            text
        )
        if cert_section_match:
            cert_text = cert_section_match.group(2)
            certs = re.split(r'[,;|•\n]', cert_text)
            for cert in certs:
                cert = cert.strip()
                if cert and len(cert) < 100:
                    certifications.append(cert)
        return certifications

    def extract_projects(self, text: str) -> List[Dict[str, Any]]:
        projects = []
        proj_section_match = re.search(
            r'(?i)(projects|portfolio|personal projects)[:\s]*([^\n]+(?:\n[^\n]+)*)',
            text
        )
        if proj_section_match:
            proj_text = proj_section_match.group(2)
            # This is a simple implementation; a more advanced parser could be used here
            project_titles = re.findall(r'([A-Z][\w\s]+)\n', proj_text)
            for title in project_titles:
                projects.append({'title': title.strip()})
        return projects

    def parse_resume(self, file_path: str, file_type: str) -> Dict[str, Any]:
        if file_type.lower() == 'pdf':
            raw_text = self.extract_text_from_pdf(file_path)
        elif file_type.lower() in ['docx', 'doc']:
            raw_text = self.extract_text_from_docx(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

        contact = self.extract_contact_info(raw_text)
        skills = self.extract_skills(raw_text)
        education = self.extract_education(raw_text)
        certifications = self.extract_certifications(raw_text)
        projects = self.extract_projects(raw_text)
        processed_text = self.preprocess_text(raw_text)

        return {
            'raw_text': raw_text,
            'processed_text': processed_text,
            'candidate_name': contact.get('name', 'Unknown'),
            'candidate_email': contact.get('email', ''),
            'phone': contact.get('phone', ''),
            'location': contact.get('location', ''),
            'skills': skills,
            'education': education,
            'experience': [],  # TODO: add timeline extraction if needed
            'projects': projects,
            'certifications': certifications
        }

    def parse_job_description(self, text: str) -> Dict[str, Any]:
        required_skills = []
        optional_skills = []
        req_match = re.search(r'(?i)(required|must have|must\.have|mandatory)[:\s]*([^\n]+(?:\n[^\n]+)*)', text)
        if req_match:
            skills_text = req_match.group(2)
            required_skills = self.extract_skills(skills_text)
        opt_match = re.search(r'(?i)(preferred|nice to have|nice.to.have|optional)[:\s]*([^\n]+(?:\n[^\n]+)*)', text)
        if opt_match:
            skills_text = opt_match.group(2)
            optional_skills = self.extract_skills(skills_text)

        exp_match = re.search(r'(\d+)[\s\-+]+(?:years?|yrs?)', text, re.IGNORECASE)
        min_experience = int(exp_match.group(1)) if exp_match else 0
        processed_text = self.preprocess_text(text)

        return {
            'raw_text': text,
            'processed_text': processed_text,
            'required_skills': required_skills if required_skills else self.extract_skills(text)[:12],
            'optional_skills': optional_skills,
            'min_experience': min_experience,
            'education_requirements': [],
            'certifications_required': [],
            'projects_required': []
        }

    def preprocess_text(self, text: str) -> str:
        text = text.lower()
        text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
        text = ' '.join(text.split())
        return text