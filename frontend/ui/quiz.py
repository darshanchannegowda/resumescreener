# frontend/ui/quiz.py
import streamlit as st
from .utils import submit_quiz_api

def display():
    st.markdown("<h2 style='color:#0b5fff'>Complete Your Quiz</h2>", unsafe_allow_html=True)

    if "quiz_questions" not in st.session_state or not st.session_state.quiz_questions:
        st.warning("No quiz found. Please apply for a job to start a quiz.")
        st.stop()

    quiz_data = st.session_state.quiz_questions
    questions = quiz_data.get("questions", [])
    answers = {}

    for i, q in enumerate(questions):
        st.markdown(f"**Question {i+1}:** {q['question']}")
        options = q['options']
        answer = st.radio(f"Options for question {i+1}", options, key=f"question_{i}")
        answers[i] = options.index(answer)

    if st.button("Submit Answers"):
        quiz_id = quiz_data.get("quiz_id")
        resume_id = quiz_data.get("resume_id")

        if quiz_id and resume_id:
            with st.spinner("Submitting answers..."):
                answer_indices = [answers[i] for i in range(len(questions))]
                resp = submit_quiz_api(quiz_id, resume_id, answer_indices)

                if resp and resp.status_code == 200:
                    st.success("Quiz submitted successfully! Your application is under review.")
                    st.session_state.quiz_questions = None
                else:
                    st.error("Failed to submit quiz.")
        else:
            st.error("Could not find quiz or resume ID to submit.")