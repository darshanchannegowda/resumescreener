# # frontend/ui/view_results.py
# import streamlit as st
# import pandas as pd
# import plotly.express as px
# from .utils import fetch_evaluations_api

# def display():
#     st.markdown("<h2 style='color:#0b5fff'>View Evaluation Results</h2>", unsafe_allow_html=True)
#     if not st.session_state.get("api_key"):
#         st.warning("Recruiter access required. Please login from the top-right.")
#         st.stop()

#     job_id = st.text_input("Job ID to fetch evaluations")
#     min_score = st.slider("Minimum Score Filter", 0, 100, 0)
#     verdict_filter = st.selectbox("Verdict Filter", ["All", "HIGH", "MEDIUM", "LOW"])

#     if st.button("Fetch Results"):
#         if not job_id:
#             st.error("Job ID required")
#         else:
#             with st.spinner("Fetching..."):
#                 resp = fetch_evaluations_api(job_id, min_score, verdict_filter if verdict_filter != "All" else None)
#                 if resp and resp.status_code == 200:
#                     evals = resp.json().get("evaluations", [])
#                     st.success(f"Found {len(evals)} evaluations.")
#                     if evals:
#                         df = pd.DataFrame(evals)
#                         st.dataframe(df)
#                         fig = px.histogram(df, x='relevance_score', nbins=20, title='Score Distribution')
#                         st.plotly_chart(fig, use_container_width=True)
#                 else:
#                     st.error("Failed to fetch results.")