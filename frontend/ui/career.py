# frontend/ui/career.py
import streamlit as st
from frontend.ui.utils import fetch_jobs, apply_to_job_api

def display():
    st.markdown("<h2 style='color:#0b5fff'>Career — Open Positions</h2>", unsafe_allow_html=True)
    jobs = fetch_jobs(limit=50)
    if not jobs:
        st.info("No active jobs available right now. Make sure the backend is running.")
    else:
        for job in jobs:
            with st.container():
                st.markdown("<div class='job-card'>", unsafe_allow_html=True)
                st.markdown(f"### {job.get('job_title', 'Untitled')}  •  {job.get('company_name','')}")
                st.markdown(f"<div class='muted'>{job.get('location','')}</div>", unsafe_allow_html=True)

                jd_preview = (job.get('raw_text','') or job.get('processed_text','') or '')[:700] + '...'
                st.write(jd_preview)

                skills = job.get('required_skills', [])[:10]
                if skills:
                    badge_html = " ".join([f"<span class='skill-badge'>{s}</span>" for s in skills])
                    st.markdown(badge_html, unsafe_allow_html=True)

                st.markdown(f"<div class='small muted'>Job ID: <code>{job.get('_id')}</code></div>", unsafe_allow_html=True)

                with st.expander("Apply"):
                    with st.form(f"apply_form_{job.get('_id')}"):
                        cand_name = st.text_input("Your name", key=f"name_{job.get('_id')}")
                        cand_email = st.text_input("Email *", key=f"email_{job.get('_id')}")
                        resume_file = st.file_uploader("Resume (PDF/DOCX) *", type=['pdf','docx','doc'], key=f"file_{job.get('_id')}")
                        submitted = st.form_submit_button("Submit Application")
                        if submitted:
                            if not cand_email or not resume_file:
                                st.error("Email and resume required")
                            else:
                                with st.spinner("Submitting application..."):
                                    resp = apply_to_job_api(job.get('_id'), resume_file, cand_email, cand_name)
                                    if resp and resp.status_code == 200:
                                        st.success("Application submitted successfully!")
                                    else:
                                        st.error("Failed to submit application.")
                st.markdown("</div>", unsafe_allow_html=True)