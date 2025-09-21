# backend/quiz_endpoints.py
import os
import uuid
import json
import requests
from typing import List, Dict, Any
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Request
from fastapi import Depends
from pydantic import BaseModel
from datetime import datetime
from bson import ObjectId

# Replace with your own DB utilities; these are placeholders that match common patterns.
# If you use the mongodb.py you uploaded, import the client/db collection objects from there.
from mongodb import get_db  # expected helper that returns a motor/mongo client or db instance

router = APIRouter()

# Config from env
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Example endpoint; you can choose the model like gemini-2.5-flash or gemini-1.5-pro depending on your quota/region.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_BASE = os.getenv("GEMINI_BASE", "https://generativelanguage.googleapis.com/v1beta/models")

if not GEMINI_API_KEY:
    # We allow service to start but will error at runtime if API key missing.
    pass

# ---------- Pydantic models ----------
class QuizQuestion(BaseModel):
    question: str
    options: List[str]         # multiple choice options
    correct_index: int = None  # keep for backend only, do not expose via /quiz

class QuizDoc(BaseModel):
    _id: str
    job_id: str
    resume_id: str
    created_at: datetime
    questions: List[QuizQuestion]
    meta: Dict[str, Any] = {}

# ---------- Helper: call Gemini generateContent ----------
def call_gemini(prompt: str, temperature: float = 0.0, max_output_tokens: int = 800) -> str:
    """
    Calls Gemini generateContent REST endpoint and returns the text result.
    See: official Gemini docs for request/response formats. Requires GEMINI_API_KEY.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set in env")

    url = f"{GEMINI_BASE}/{GEMINI_MODEL}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY
    }

    body = {
        "prompt": {
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": prompt}]}
            ]
        },
        "temperature": temperature,
        "maxOutputTokens": max_output_tokens
    }

    resp = requests.post(url, headers=headers, json=body, timeout=60)
    if not resp.ok:
        raise HTTPException(status_code=502, detail=f"Gemini API error: {resp.status_code} {resp.text}")

    data = resp.json()
    # The exact path to text may vary by response shape; this follows typical responses.
    # Inspect data to adjust if your model/endpoint responds differently.
    # This picks textual content from the first candidate.
    try:
        text = ""
        # Multiple response formats exist; handle common one:
        if "candidates" in data and data["candidates"]:
            for c in data["candidates"]:
                if "output" in c and isinstance(c["output"], list):
                    for item in c["output"]:
                        if item.get("type") == "text":
                            text += item.get("text", "")
        elif "output" in data and isinstance(data["output"], list):
            for item in data["output"]:
                if item.get("type") == "text":
                    text += item.get("text", "")
        else:
            # Fallback: stringified json
            text = json.dumps(data)
        return text.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse Gemini response: {str(e)}")

# ---------- Utility: generate MCQs from JD & resume ----------
def generate_quiz_from_text(job_text: str, resume_text: str, n_questions: int = 5) -> List[QuizQuestion]:
    """
    Use Gemini to produce n multiple-choice questions relevant to the job_text and optionally tailored
    slightly to the resume_text (to probe candidate's claimed skills).
    The Gemini output will be parsed; the prompt asks for JSON to make parsing reliable.
    """
    system_prompt = (
        "You are an assistant that generates short multiple-choice skill-check questions (MCQs) for job applicants. "
        "Produce exactly a JSON array of questions. Each question object must have: "
        '"question" (string), "options" (array of 3-5 strings), "correct_index" (0-based integer).'
        "Make the questions directly testable short knowledge or application of skills mentioned in the job description. "
        "If the candidate's resume includes specific tools or versions, prefer questions that check those tools/skills."
    )

    user_prompt = (
        f"{system_prompt}\n\n"
        f"Job description:\n{job_text}\n\n"
        f"Candidate resume (short):\n{resume_text}\n\n"
        f"Return exactly {n_questions} questions in JSON only; do not add any extra commentary."
    )

    raw = call_gemini(user_prompt, temperature=0.1, max_output_tokens=900)

    # Attempt to extract JSON from the model text. Model is asked to only respond with JSON, but robust-parse anyway.
    try:
        # find first json bracket
        start = raw.find("[")
        end = raw.rfind("]") + 1
        raw_json = raw[start:end]
        parsed = json.loads(raw_json)
        questions = []
        for q in parsed:
            qq = QuizQuestion(
                question=q.get("question"),
                options=q.get("options") or [],
                correct_index=int(q.get("correct_index")) if q.get("correct_index") is not None else None
            )
            questions.append(qq)
        return questions
    except Exception:
        # Fallback: if parsing fails, do a naive parse split (less reliable), but still produce something
        raise HTTPException(status_code=500, detail="Failed to parse JSON from Gemini when generating quiz. Response: " + raw[:1000])

# ---------- Utility: evaluate answers ----------
def evaluate_answers_with_gemini(questions: List[QuizQuestion], user_answers: List[int], user_text_answers: List[str]=None) -> Dict[str, Any]:
    """
    Evaluate user's selected choice indices against the correct answers, and use Gemini to provide
    an explanatory score and short feedback. Returns per-question results and overall score.
    For MCQs we compare indices (fast). For free-text evaluation (if you want open answers), we can send
    the user's text and the ideal answer to Gemini to get a quality score.
    """
    # Basic scoring for MCQs:
    results = []
    total = 0
    max_total = len(questions) * 1  # 1 point per question

    # Prepare a small prompt to ask Gemini to verify and provide feedback.
    verify_entries = []
    for i, q in enumerate(questions):
        correct_idx = q.correct_index if q.correct_index is not None else -1
        chosen_idx = user_answers[i] if i < len(user_answers) else None
        correct = (chosen_idx == correct_idx)
        score = 1 if correct else 0
        total += score
        entry = {
            "index": i,
            "question": q.question,
            "options": q.options,
            "correct_index": correct_idx,
            "chosen_index": chosen_idx,
            "is_correct": correct
        }
        verify_entries.append(entry)

    # Get brief feedback from Gemini: explanation for each question and a short improvement tip
    prompt_parts = [
        "You are an assistant that evaluates MCQ quiz attempts. For every question entry provided below,",
        "respond with a JSON array of same length with objects that have fields: 'explanation' and 'tip'.",
        "The 'explanation' should say why the correct option is correct (one or two sentences). The 'tip' should be a short study tip if the candidate was incorrect, otherwise empty string."
    ]
    prompt_parts.append("Entries:\n" + json.dumps(verify_entries, indent=2))
    prompt = "\n\n".join(prompt_parts)

    raw = call_gemini(prompt, temperature=0.0, max_output_tokens=800)
    try:
        # extract JSON similarly
        start = raw.find("[")
        end = raw.rfind("]") + 1
        parsed = json.loads(raw[start:end])
    except Exception:
        parsed = [{"explanation": "", "tip": ""} for _ in verify_entries]

    per_q_results = []
    for idx, v in enumerate(verify_entries):
        feedback = parsed[idx] if idx < len(parsed) else {"explanation": "", "tip": ""}
        per_q_results.append({
            "index": v["index"],
            "question": v["question"],
            "chosen_index": v["chosen_index"],
            "correct_index": v["correct_index"],
            "is_correct": v["is_correct"],
            "explanation": feedback.get("explanation", ""),
            "tip": feedback.get("tip", "")
        })

    score_pct = int((total / max_total) * 100) if max_total > 0 else 0

    return {
        "score_raw": total,
        "score_pct": score_pct,
        "per_question": per_q_results,
        "max_score": max_total
    }

# ---------- API endpoints ----------

@router.post("/apply")
async def apply_and_create_quiz(
    request: Request,
    job_id: str = Form(...),
    candidate_email: str = Form(...),
    candidate_name: str = Form(...),
    file: UploadFile = File(...)
):
    """
    Accepts application + resume file, stores resume, triggers quiz creation via Gemini and returns quiz_id + resume_id.
    Frontend expects JSON with quiz_id and resume_id and (optionally) questions.
    """
    db = get_db()
    # Read resume bytes and (optionally) parse text using your parser utilities
    resume_bytes = await file.read()
    # Save resume to DB or file storage
    resume_doc = {
        "candidate_name": candidate_name,
        "candidate_email": candidate_email,
        "filename": file.filename,
        "content_bytes": resume_bytes,  # consider storing in GridFS or external storage in prod
        "created_at": datetime.utcnow()
    }
    res = db["resumes"].insert_one(resume_doc)
    resume_id = str(res.inserted_id)

    # Pull job description from jobs collection
    job_doc = db["jobs"].find_one({"_id": ObjectId(job_id)})
    if not job_doc:
        raise HTTPException(status_code=404, detail="Job not found")

    job_text = job_doc.get("raw_text") or job_doc.get("processed_text") or job_doc.get("job_description") or ""
    # Optionally produce a concise resume_text by calling your parser logic. We'll use a short placeholder.
    resume_text = "(parsed resume text unavailable)"  # replace with your parser.parse_resume(resume_bytes) if available

    # generate quiz
    n_questions = 5
    try:
        questions = generate_quiz_from_text(job_text, resume_text, n_questions=n_questions)
    except HTTPException as e:
        # if Gemini generation fails, fallback to an empty quiz or simple skill checks
        raise

    quiz_id = str(uuid.uuid4())
    quiz_doc = {
        "_id": quiz_id,
        "job_id": job_id,
        "resume_id": resume_id,
        "created_at": datetime.utcnow(),
        "questions": [q.dict() for q in questions],
        "meta": {"generated_by": "gemini", "model": GEMINI_MODEL}
    }
    db["quizzes"].insert_one(quiz_doc)

    # Return quiz id (do NOT send correct_index back in the quiz fetch endpoint)
    return {"quiz_id": quiz_id, "resume_id": resume_id, "job_id": job_id}

@router.get("/quiz/{quiz_id}")
async def get_quiz(quiz_id: str):
    """Return quiz to candidate, but strip correct_index from payload."""
    db = get_db()
    qdoc = db["quizzes"].find_one({"_id": quiz_id})
    if not qdoc:
        raise HTTPException(status_code=404, detail="Quiz not found")
    questions = qdoc.get("questions", [])
    # Remove correct_index before returning
    public_questions = []
    for q in questions:
        qcopy = dict(q)
        qcopy.pop("correct_index", None)
        public_questions.append({
            "question": qcopy.get("question"),
            "options": qcopy.get("options")
        })
    return {"quiz_id": quiz_id, "job_id": qdoc.get("job_id"), "resume_id": qdoc.get("resume_id"), "questions": public_questions}

@router.post("/submit-quiz")
async def submit_quiz(quiz_id: str, resume_id: str, request: Request):
    """
    Expects answers as query params like answers[0]=1&answers[1]=2 (frontend utils prepares that).
    Gather answers, use Gemini to provide explanations and compute score, store evaluation and return results.
    """
    db = get_db()
    qdoc = db["quizzes"].find_one({"_id": quiz_id})
    if not qdoc:
        raise HTTPException(status_code=404, detail="Quiz not found")

    # Parse answers from query parameters
    params = dict(request.query_params)
    # answers are passed as answers[0]=idx, answers[1]=idx, etc.
    answers = []
    i = 0
    while True:
        key = f"answers[{i}]"
        if key in params:
            try:
                answers.append(int(params[key]))
            except Exception:
                answers.append(None)
            i += 1
        else:
            break

    # Evaluate answers
    questions = [QuizQuestion(**q) for q in qdoc.get("questions", [])]
    eval_result = evaluate_answers_with_gemini(questions, answers)

    # Store evaluation
    eval_doc = {
        "quiz_id": quiz_id,
        "resume_id": resume_id,
        "job_id": qdoc.get("job_id"),
        "score_raw": eval_result["score_raw"],
        "score_pct": eval_result["score_pct"],
        "per_question": eval_result["per_question"],
        "created_at": datetime.utcnow(),
        "meta": {"evaluated_by": "gemini", "model": GEMINI_MODEL}
    }
    db["evaluations"].insert_one(eval_doc)

    return {"evaluation": eval_result, "stored": True}
