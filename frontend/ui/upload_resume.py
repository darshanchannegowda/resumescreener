# frontend/ui/upload_resume.py
import streamlit as st
from .utils import fetch_jobs, apply_to_job_api, bulk_upload_resumes_api

def display():
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("### Apply for a Job")
    st.caption("Upload a resume to apply")

    jobs = fetch_jobs(limit=50)
    job_map = {f"{j.get('job_title','Untitled')} — {j.get('company_name','Company')}": j for j in jobs}
    choice = st.selectbox("Select a job", list(job_map.keys()) or ["No jobs available"])
    job = job_map.get(choice)

    name = st.text_input("Full name")
    email = st.text_input("Email")
    file = st.file_uploader("Upload resume (PDF/DOCX)", type=["pdf", "docx"])

    apply_col, _ = st.columns([1, 3])
    with apply_col:
        if st.button("Apply", disabled=not (job and file and email and name)):
            with st.spinner("Submitting application..."):
                resp = apply_to_job_api(
                    job_id=job.get("_id", ""),
                    file=file,
                    candidate_email=email,
                    candidate_name=name
                )
                if not resp or not resp.ok:
                    st.error("Application failed. Please check details and try again.")
                else:
                    st.success("Application submitted successfully!")

    st.markdown("</div>", unsafe_allow_html=True)

    # --- BULK UPLOAD SECTION (LOGGED-IN RECRUITERS ONLY) ---
    if st.session_state.get("api_key"):
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("### Bulk Upload Resumes")
        st.caption("For internal use: upload multiple resumes to a job without name/email.")

        bulk_job_choice = st.selectbox("Select a job for bulk upload", list(job_map.keys()) or ["No jobs available"], key="bulk_job_select")
        bulk_job = job_map.get(bulk_job_choice)

        uploaded_files = st.file_uploader(
            "Upload resume files (PDF/DOCX)",
            type=["pdf", "docx"],
            accept_multiple_files=True,
            key="bulk_file_uploader"
        )

        if st.button("Upload Resumes", key="bulk_upload_button", disabled=not (bulk_job and uploaded_files)):
            with st.spinner(f"Uploading {len(uploaded_files)} resumes..."):
                resp = bulk_upload_resumes_api(job_id=bulk_job.get("_id", ""), files=uploaded_files)
                if resp and resp.status_code == 200:
                    st.success(f"Successfully uploaded {len(uploaded_files)} resumes.")
                else:
                    st.error("Bulk upload failed. Please try again.")
        st.markdown("</div>", unsafe_allow_html=True)