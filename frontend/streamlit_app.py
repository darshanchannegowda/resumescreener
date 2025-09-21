# frontend/streamlit_app.py
import streamlit as st
from frontend.ui import home, career, upload_resume, create_job, evaluate_resumes, header
from frontend.ui.styles import load_css
import extra_streamlit_components as stx
import json
import datetime

# Defensive initialization so recruiter_info is always a dict
if "recruiter_info" not in st.session_state or st.session_state.get("recruiter_info") is None:
    st.session_state["recruiter_info"] = {}


st.set_page_config(
    page_title="Resume Relevance Check System",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="collapsed"
)


def get_cookie_manager():
    return stx.CookieManager()

cookie_manager = get_cookie_manager()

# Load custom CSS
load_css()

# Initialize session state from cookies
if "api_key" not in st.session_state or st.session_state.api_key is None:
    api_key_from_cookie = cookie_manager.get(cookie="api_key")
    if api_key_from_cookie:
        st.session_state["api_key"] = api_key_from_cookie
        recruiter_info_from_cookie = cookie_manager.get(cookie="recruiter_info")
        if recruiter_info_from_cookie:
            try:
                st.session_state["recruiter_info"] = json.loads(recruiter_info_from_cookie)
            except json.JSONDecodeError:
                st.session_state["recruiter_info"] = None
        else:
            st.session_state["recruiter_info"] = None
    else:
        st.session_state["api_key"] = None
        st.session_state["recruiter_info"] = None


# Display header
header.display()

# Navigation
if st.session_state.get("api_key"):
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Go to",
        ["Home", "Career", "Upload Resume", "Create Job", "Evaluate Resumes"],
        index=0
    )
else:
    page = st.selectbox("Go to", ["Home", "Career", "Upload Resume"])

# Page rendering
if page == "Home":
    home.display()
elif page == "Career":
    career.display()
elif page == "Upload Resume":
    upload_resume.display()
elif page == "Create Job":
    create_job.display()
elif page == "Evaluate Resumes":
    evaluate_resumes.display()


