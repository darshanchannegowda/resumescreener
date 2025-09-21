# frontend/ui/header.py
import streamlit as st
import requests
from .utils import API_BASE_URL
import extra_streamlit_components as stx
import json
import datetime


def get_cookie_manager():
    return stx.CookieManager()

cookie_manager = get_cookie_manager()

def display():
    header_cols = st.columns([0.8, 4, 1.2])
    with header_cols[0]:
        st.image("http://innomatics.in/wp-content/uploads/2023/01/Innomatics-Logo1.png", width=181)
    with header_cols[1]:
        st.markdown("<div class='app-header'><div class='app-title'>📝 Resume Relevance Check System</div><div class='app-sub'>Innomatics Research Labs — AI-powered resume evaluation & upskilling</div></div>", unsafe_allow_html=True)

    with header_cols[2]:
        with st.expander("Employee / Recruiter", expanded=False):
            if st.session_state.get("api_key"):
                recruiter_name = "User"
                recruiter_info = st.session_state.get('recruiter_info')
                if isinstance(recruiter_info, dict):
                    recruiter_name = recruiter_info.get('name', 'User')

                st.markdown(f"**Logged in** as `{recruiter_name}`")
                if st.button("Logout"):
                    st.session_state["api_key"] = None
                    st.session_state["recruiter_info"] = None
                    cookie_manager.delete("api_key")
                    cookie_manager.delete("recruiter_info")
                    st.rerun()
            else:
                emp_email = st.text_input("Email (employee)")
                emp_password = st.text_input("Password", type="password")
                if st.button("Login as Employee"):
                    try:
                        resp = requests.post(f"{API_BASE_URL}/employee/login", json={"email": emp_email, "password": emp_password})
                        if resp.ok:
                            api_key = resp.json().get("emp_api_key")
                            recruiter_info = resp.json().get("employee")

                            st.session_state["api_key"] = api_key
                            st.session_state["recruiter_info"] = recruiter_info

                            # Set cookies for persistence
                            cookie_manager.set("api_key", api_key, expires_at=datetime.datetime.now() + datetime.timedelta(days=30))
                            cookie_manager.set("recruiter_info", json.dumps(recruiter_info), expires_at=datetime.datetime.now() + datetime.timedelta(days=30))

                            st.rerun()
                        else:
                            st.error("Login failed.")
                    except requests.RequestException:
                        st.error("Connection error.")