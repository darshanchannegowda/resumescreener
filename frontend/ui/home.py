# frontend/ui/home.py
import streamlit as st

def display():
    """Displays the home page."""
    st.markdown("<h1 style='text-align: center;'>Resume Relevance Check System</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Welcome! Use the navigation to get started.</p>", unsafe_allow_html=True)

    st.markdown("""
    <div class='hero'>
    This system helps you to:
    <ul>
        <li><b>View and apply for jobs:</b> Check out the 'Career' page.</li>
        <li><b>For Recruiters:</b> Log in to create job postings, evaluate resumes, and view evaluation results.</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)