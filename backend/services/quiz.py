# backend/services/quiz.py
import random
import uuid
from typing import List, Dict, Any
import google.generativeai as genai
from backend.config import Config
import json
import logging

logger = logging.getLogger(__name__)

# Configure the generative AI model
if Config.GEMINI_API_KEY:
    genai.configure(api_key=Config.GEMINI_API_KEY)

class QuizService:
    def __init__(self):
        if Config.GEMINI_API_KEY:
            self.model = genai.GenerativeModel('gemini-pro')
        else:
            self.model = None

    def _normalize_skill(self, s: str) -> str:
        return s.strip().lower()

    def select_questions(self, job_desc: Dict[str, Any], resume: Dict[str, Any], num_questions: int = 3) -> List[Dict[str, Any]]:
        if not self.model:
            logger.warning("GEMINI_API_KEY not configured. Skipping LLM question generation.")
            return []

        job_skills = [self._normalize_skill(s) for s in job_desc.get("required_skills", [])]
        resume_skills = [self._normalize_skill(s) for s in resume.get("skills", [])]

        # Prioritize overlapping skills
        overlapped = list(set(job_skills) & set(resume_skills))

        # Fallback to job skills if no overlap
        if not overlapped:
            overlapped = job_skills

        if not overlapped:
            logger.warning("No skills found to generate questions.")
            return []

        # Generate questions using the LLM
        prompt = self._generate_prompt(job_desc.get('raw_text', ''), resume.get('raw_text', ''), overlapped, num_questions)

        try:
            response = self.model.generate_content(prompt)
            # Clean the response to extract the JSON part
            cleaned_response = response.text.strip().replace('```json', '').replace('```', '').strip()
            questions = json.loads(cleaned_response)

            # Add unique IDs to the questions
            for q in questions:
                q['quiz_qid'] = str(uuid.uuid4())
                q['bank_qid'] = None  # No longer from a static bank

            return questions
        except Exception as e:
            # --- MODIFICATION ---
            # Log the actual error for easier debugging
            logger.error(f"Failed to generate or parse LLM response. Error: {e}") 
            # --- END MODIFICATION ---
            return []

    def _generate_prompt(self, job_text: str, resume_text: str, skills: List[str], num_questions: int) -> str:
        prompt = f"""
        Based on the following job description and resume, generate {num_questions} multiple-choice questions to assess the candidate's skills. The questions should be relevant to the most important skills mentioned in the job description that are also present in the resume.

        **Job Description:**
        {job_text[:1000]}

        **Resume:**
        {resume_text[:1000]}

        **Focus on these skills:** {', '.join(skills)}

        Please provide the output in a valid JSON format as a list of objects, where each object has the following keys:
        - "skill": The skill being tested (string).
        - "question": The question text (string).
        - "options": A list of 4 strings representing the possible answers.
        - "answer_index": The index (0-3) of the correct answer in the "options" list (integer).

        Example format:
        ```json
        [
          {{
            "skill": "Python",
            "question": "What is a decorator in Python?",
            "options": [
              "A function that takes another function and extends its behavior without explicitly modifying it",
              "A way to create a list of numbers",
              "A data type for storing key-value pairs",
              "A method for handling exceptions"
            ],
            "answer_index": 0
          }}
        ]
        ```
        """
        return prompt