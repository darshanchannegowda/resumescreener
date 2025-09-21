# frontend/ui/evaluate_resumes.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from .utils import evaluate_single_api, evaluate_batch_api, fetch_jobs, fetch_resumes_api

def display():
    st.markdown("<h2 style='color:#0b5fff; margin-bottom: 2rem;'>Resume Evaluation Dashboard</h2>", unsafe_allow_html=True)
    
    # Authentication check
    if not st.session_state.get("api_key"):
        st.error("🔒 Recruiter access required. Please login from the top-right.")
        st.stop()

    # Initialize session state for results
    if 'batch_results' not in st.session_state:
        st.session_state.batch_results = None
    if 'single_result' not in st.session_state:
        st.session_state.single_result = None

    # Sidebar for filters (when batch results exist)
    with st.sidebar:
        if st.session_state.batch_results:
            st.markdown("### 🔍 Advanced Filters")
            
            # Score range filter
            score_range = st.slider(
                "Relevance Score Range",
                min_value=0.0,
                max_value=100.0,
                value=(0.0, 100.0),
                step=1.0,
                key="score_filter"
            )
            
            # Verdict filter
            verdict_options = st.multiselect(
                "Filter by Verdict",
                options=['HIGH', 'MEDIUM', 'LOW'],
                default=['HIGH', 'MEDIUM', 'LOW'],
                key="verdict_filter"
            )
            
            # Experience range filter
            exp_range = st.slider(
                "Experience Range (Years)",
                min_value=0,
                max_value=50,
                value=(0, 50),
                step=1,
                key="exp_filter"
            )
            
            # Skills filter
            if st.session_state.batch_results:
                all_skills = set()
                for eval_data in st.session_state.batch_results.get('evaluations', []):
                    all_skills.update(eval_data.get('analysis', {}).get('matched_skills', []))
                
                skill_filter = st.multiselect(
                    "Filter by Matched Skills",
                    options=list(all_skills),
                    key="skill_filter"
                )

    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col2:
        # Quick stats metrics (when batch results exist)
        if st.session_state.batch_results:
            summary = st.session_state.batch_results.get('summary', {})
            st.metric(
                label="📊 Total Evaluated", 
                value=st.session_state.batch_results.get('total_evaluated', 0)
            )
            st.metric(
                label="🎯 High Matches", 
                value=summary.get('high_matches', 0),
                delta=f"{(summary.get('high_matches', 0) / max(st.session_state.batch_results.get('total_evaluated', 1), 1) * 100):.1f}%"
            )
            st.metric(
                label="⚡ Medium Matches", 
                value=summary.get('medium_matches', 0)
            )
            st.metric(
                label="❌ Low Matches", 
                value=summary.get('low_matches', 0)
            )

    # Main evaluation tabs
    tab1, tab2, tab3 = st.tabs(["🔍 Single Evaluation", "📊 Batch Evaluation", "📈 Analytics"])

    with tab1:
        st.markdown("### Single Resume Evaluation")
        
        # Fetch data
        try:
            with st.spinner("Loading data..."):
                jobs = fetch_jobs(limit=200)
                resumes = fetch_resumes_api(limit=10)
        except Exception as e:
            st.error(f"❌ Error loading data: {str(e)}")
            return

        # Create selection options
        job_options = {f"{j.get('job_title', 'N/A')} — {j.get('company_name', 'N/A')} ({j.get('_id', 'N/A')})": j.get('_id') for j in jobs}
        resume_options = {f"{r.get('candidate_name', 'N/A')} ({r.get('candidate_email', 'N/A')})": r.get('_id') for r in resumes}

        # Selection inputs
        col1, col2 = st.columns(2)
        with col1:
            selected_resume_label = st.selectbox(
                "📄 Select Resume", 
                ["-- Select a resume --"] + list(resume_options.keys()),
                key="single_resume_select"
            )
        
        with col2:
            selected_job_label = st.selectbox(
                "💼 Select Job", 
                ["-- Select a job --"] + list(job_options.keys()),
                key="single_job_select"
            )

        # Evaluate button
        if st.button("🚀 Evaluate Resume", type="primary", use_container_width=True):
            if selected_resume_label == "-- Select a resume --" or selected_job_label == "-- Select a job --":
                st.error("❌ Please select both a resume and a job position")
            else:
                resume_id = resume_options[selected_resume_label]
                job_id = job_options[selected_job_label]
                
                with st.spinner("🔄 Evaluating resume..."):
                    try:
                        resp = evaluate_single_api(resume_id, job_id)
                        if resp and resp.status_code == 200:
                            result = resp.json().get("evaluation", {})
                            st.session_state.single_result = result
                            st.success("✅ Evaluation completed successfully!")
                        else:
                            st.error(f"❌ Evaluation failed. Status: {resp.status_code if resp else 'No response'}")
                    except Exception as e:
                        st.error(f"❌ Error during evaluation: {str(e)}")

        # Display single evaluation results
        if st.session_state.single_result:
            display_single_evaluation_result(st.session_state.single_result)

    with tab2:
        st.markdown("### Batch Resume Evaluation")
        
        # Job selection for batch
        selected_job_label_batch = st.selectbox(
            "💼 Select Job for Batch Evaluation", 
            ["-- Select a job --"] + list(job_options.keys()) if 'job_options' in locals() else ["-- No jobs available --"],
            key="batch_job_select"
        )
        
        # Batch evaluation button
        if st.button("🚀 Run Batch Evaluation", type="primary", use_container_width=True):
            if selected_job_label_batch == "-- Select a job --":
                st.error("❌ Please select a job position for batch evaluation")
            else:
                job_id_batch = job_options[selected_job_label_batch]
                
                with st.spinner("🔄 Running batch evaluation... This may take a while."):
                    try:
                        resp = evaluate_batch_api(job_id_batch)
                        if resp and resp.status_code == 200:
                            st.session_state.batch_results = resp.json()
                            st.success("✅ Batch evaluation completed successfully!")
                            st.rerun()  # Refresh to show results
                        else:
                            st.error(f"❌ Batch evaluation failed. Status: {resp.status_code if resp else 'No response'}")
                    except Exception as e:
                        st.error(f"❌ Error during batch evaluation: {str(e)}")

        # Display batch results
        if st.session_state.batch_results:
            display_batch_evaluation_results(st.session_state.batch_results)

    with tab3:
        if st.session_state.batch_results:
            display_analytics_dashboard(st.session_state.batch_results)
        else:
            st.info("📊 Run a batch evaluation first to see analytics")

def display_single_evaluation_result(result):
    """Display single evaluation result in a professional format"""
    st.markdown("---")
    st.markdown("### 📊 Evaluation Results")
    
    # Key metrics in columns
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🎯 Relevance Score", f"{result.get('relevance_score', 0):.1f}%")
    with col2:
        st.metric("💪 Hard Match", f"{result.get('hard_match_score', 0):.1f}%")
    with col3:
        st.metric("🌟 Soft Match", f"{result.get('soft_match_score', 0):.1f}%")
    with col4:
        verdict = result.get('verdict', 'N/A')
        color = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴"}.get(verdict, "⚪")
        st.metric("📝 Verdict", f"{color} {verdict}")

    # Analysis details
    analysis = result.get('analysis', {})
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### ✅ Matched Skills")
        matched_skills = analysis.get('matched_skills', [])
        if matched_skills:
            for skill in set(matched_skills):  # Remove duplicates
                st.markdown(f"• {skill}")
        else:
            st.markdown("*No matched skills found*")
    
    with col2:
        st.markdown("#### ❌ Missing Skills")
        missing_skills = analysis.get('missing_skills', [])
        if missing_skills:
            for skill in missing_skills:
                st.markdown(f"• {skill}")
        else:
            st.markdown("*No missing skills*")

    # Experience analysis
    exp_details = analysis.get('experience_details', {})
    if exp_details:
        st.markdown("#### 💼 Experience Analysis")
        resume_exp = exp_details.get('resume_experience', 'N/A')
        required_exp = exp_details.get('required_experience', 'N/A')
        st.markdown(f"**Resume Experience:** {resume_exp} years")
        st.markdown(f"**Required Experience:** {required_exp}")

    # Feedback
    feedback = result.get('feedback', {})
    if feedback:
        st.markdown("#### 💡 Feedback")
        
        strengths = feedback.get('strengths', [])
        if strengths:
            st.markdown("**Strengths:**")
            for strength in strengths:
                st.markdown(f"✅ {strength}")
        
        improvements = feedback.get('improvements', [])
        if improvements:
            st.markdown("**Areas for Improvement:**")
            for improvement in improvements:
                st.markdown(f"🔄 {improvement}")
        
        suggestions = feedback.get('suggestions', [])
        if suggestions:
            st.markdown("**Suggestions:**")
            for suggestion in suggestions:
                st.markdown(f"💡 {suggestion}")

def display_batch_evaluation_results(batch_results):
    """Display batch evaluation results with advanced filtering and sorting"""
    st.markdown("---")
    st.markdown("### 📊 Batch Evaluation Results")
    
    # Convert to DataFrame for easier manipulation
    evaluations = batch_results.get('evaluations', [])
    if not evaluations:
        st.warning("⚠️ No evaluation results found")
        return
    
    df = pd.DataFrame(evaluations)
    
    # Apply filters from sidebar
    filtered_df = df[
        (df['relevance_score'] >= st.session_state.get('score_filter', [0, 100])[0]) &
        (df['relevance_score'] <= st.session_state.get('score_filter', [0, 100])[1]) &
        (df['verdict'].isin(st.session_state.get('verdict_filter', ['HIGH', 'MEDIUM', 'LOW'])))
    ]
    
    # Experience filter
    if 'experience_details' in df.columns:
        exp_filter = st.session_state.get('exp_filter', [0, 50])
        filtered_df = filtered_df[
            filtered_df['analysis'].apply(
                lambda x: exp_filter[0] <= x.get('experience_details', {}).get('resume_experience', 0) <= exp_filter[1]
            )
        ]
    
    # Skill filter
    skill_filter = st.session_state.get('skill_filter', [])
    if skill_filter:
        filtered_df = filtered_df[
            filtered_df['analysis'].apply(
                lambda x: any(skill in x.get('matched_skills', []) for skill in skill_filter)
            )
        ]
    
    # Sorting options
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        sort_by = st.selectbox(
            "📈 Sort by",
            options=['relevance_score', 'hard_match_score', 'soft_match_score', 'verdict'],
            index=0,
            key="sort_option"
        )
    
    with col2:
        sort_order = st.selectbox(
            "📊 Order",
            options=['Descending', 'Ascending'],
            key="sort_order"
        )
    
    with col3:
        show_count = st.selectbox(
            "📄 Show",
            options=[10, 25, 50, 100, 'All'],
            key="show_count"
        )
    
    # Sort the dataframe
    ascending = sort_order == 'Ascending'
    filtered_df = filtered_df.sort_values(by=sort_by, ascending=ascending)
    
    # Limit results
    if show_count != 'All':
        filtered_df = filtered_df.head(show_count)
    
    st.markdown(f"**Showing {len(filtered_df)} of {len(df)} total evaluations**")
    
    # Create display table
    display_df = create_display_dataframe(filtered_df)
    
    # Display the table
    st.dataframe(
        display_df,
        use_container_width=True,
        height=600,
        column_config={
            "Relevance Score": st.column_config.ProgressColumn(
                "Relevance Score",
                help="Overall relevance score",
                min_value=0,
                max_value=100,
                format="%.1f%%"
            ),
            "Hard Match": st.column_config.ProgressColumn(
                "Hard Match",
                help="Hard skills match score",
                min_value=0,
                max_value=100,
                format="%.1f%%"
            ),
            "Soft Match": st.column_config.ProgressColumn(
                "Soft Match", 
                help="Soft skills match score",
                min_value=0,
                max_value=100,
                format="%.1f%%"
            ),
            "Verdict": st.column_config.TextColumn(
                "Verdict",
                help="Final verdict",
                width="small"
            )
        }
    )
    
    # Export functionality
    if st.button("📥 Export Results to CSV", use_container_width=True):
        csv = display_df.to_csv(index=False)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            label="💾 Download CSV File",
            data=csv,
            file_name=f"batch_evaluation_results_{timestamp}.csv",
            mime="text/csv",
            use_container_width=True
        )

def create_display_dataframe(df):
    """Create a clean dataframe for display"""
    display_data = []
    
    for _, row in df.iterrows():
        analysis = row.get('analysis', {})
        matched_skills = list(set(analysis.get('matched_skills', [])))  # Remove duplicates
        missing_skills = analysis.get('missing_skills', [])
        exp_details = analysis.get('experience_details', {})
        
        display_data.append({
            'Resume ID': row.get('resume_id', '')[:8] + '...',
            'Relevance Score': row.get('relevance_score', 0),
            'Hard Match': row.get('hard_match_score', 0),
            'Soft Match': row.get('soft_match_score', 0),
            'Verdict': row.get('verdict', ''),
            'Matched Skills': ', '.join(matched_skills[:3]) + ('...' if len(matched_skills) > 3 else ''),
            'Missing Skills': ', '.join(missing_skills[:2]) + ('...' if len(missing_skills) > 2 else ''),
            'Experience': f"{exp_details.get('resume_experience', 'N/A')} years",
            'Evaluated At': pd.to_datetime(row.get('evaluated_at', '')).strftime('%Y-%m-%d %H:%M') if row.get('evaluated_at') else 'N/A'
        })
    
    return pd.DataFrame(display_data)

def display_analytics_dashboard(batch_results):
    """Display analytics charts and insights"""
    st.markdown("### 📈 Analytics Dashboard")
    
    evaluations = batch_results.get('evaluations', [])
    if not evaluations:
        st.warning("⚠️ No data available for analytics")
        return
    
    df = pd.DataFrame(evaluations)
    
    # Summary statistics
    col1, col2 = st.columns(2)
    
    with col1:
        # Score distribution
        fig_hist = px.histogram(
            df, 
            x='relevance_score',
            nbins=20,
            title='📊 Relevance Score Distribution',
            labels={'relevance_score': 'Relevance Score (%)', 'count': 'Number of Candidates'}
        )
        fig_hist.update_layout(height=400)
        st.plotly_chart(fig_hist, use_container_width=True)
    
    with col2:
        # Verdict distribution
        verdict_counts = df['verdict'].value_counts()
        fig_pie = px.pie(
            values=verdict_counts.values,
            names=verdict_counts.index,
            title='🎯 Verdict Distribution',
            color_discrete_map={'HIGH': '#00CC96', 'MEDIUM': '#FFA15A', 'LOW': '#EF553B'}
        )
        fig_pie.update_layout(height=400)
        st.plotly_chart(fig_pie, use_container_width=True)
    
    # Score comparison
    fig_scatter = px.scatter(
        df,
        x='hard_match_score',
        y='soft_match_score',
        color='verdict',
        size='relevance_score',
        title='💪 Hard vs Soft Skills Match',
        labels={
            'hard_match_score': 'Hard Match Score (%)',
            'soft_match_score': 'Soft Match Score (%)'
        },
        color_discrete_map={'HIGH': '#00CC96', 'MEDIUM': '#FFA15A', 'LOW': '#EF553B'}
    )
    fig_scatter.update_layout(height=500)
    st.plotly_chart(fig_scatter, use_container_width=True)
    
    # Top skills analysis
    all_skills = []
    for evaluation in evaluations:
        matched_skills = evaluation.get('analysis', {}).get('matched_skills', [])
        all_skills.extend(matched_skills)
    
    if all_skills:
        skill_counts = pd.Series(all_skills).value_counts().head(10)
        fig_bar = px.bar(
            x=skill_counts.values,
            y=skill_counts.index,
            orientation='h',
            title='🔥 Top 10 Most Matched Skills',
            labels={'x': 'Frequency', 'y': 'Skills'}
        )
        fig_bar.update_layout(height=400)
        st.plotly_chart(fig_bar, use_container_width=True)

    # Experience vs Score analysis
    exp_data = []
    for evaluation in evaluations:
        exp_details = evaluation.get('analysis', {}).get('experience_details', {})
        resume_exp = exp_details.get('resume_experience', 0)
        if isinstance(resume_exp, (int, float)) and resume_exp <= 50:  # Filter outliers
            exp_data.append({
                'experience': resume_exp,
                'relevance_score': evaluation.get('relevance_score', 0),
                'verdict': evaluation.get('verdict', '')
            })
    
    if exp_data:
        exp_df = pd.DataFrame(exp_data)
        fig_exp = px.scatter(
            exp_df,
            x='experience',
            y='relevance_score',
            color='verdict',
            title='💼 Experience vs Relevance Score',
            labels={'experience': 'Years of Experience', 'relevance_score': 'Relevance Score (%)'},
            color_discrete_map={'HIGH': '#00CC96', 'MEDIUM': '#FFA15A', 'LOW': '#EF553B'}
        )
        fig_exp.update_layout(height=400)
        st.plotly_chart(fig_exp, use_container_width=True)
