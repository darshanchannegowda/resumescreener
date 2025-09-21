# frontend/ui/create_job.py
import streamlit as st
import os
import tempfile
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from frontend.ui.utils import create_job_api
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini AI
try:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
    else:
        st.warning("⚠️ GEMINI_API_KEY not found in environment variables. Document parsing will be disabled.")
        GEMINI_API_KEY = None
except Exception as e:
    st.error(f"❌ Error configuring Gemini AI: {str(e)}")
    GEMINI_API_KEY = None


# Safe helper for session state nested lookups
def ss_get_nested(session_key: str, nested_key: str, default=""):
    """
    Return st.session_state[session_key][nested_key] if present and not None,
    otherwise return default.
    """
    root = st.session_state.get(session_key) or {}
    try:
        return root.get(nested_key, default)
    except AttributeError:
        # In case the root isn't a dict (defensive)
        return default


class JobDescriptionParser:
    """Enhanced job description parser using Gemini AI"""
    
    def __init__(self):
        if GEMINI_API_KEY:
            try:
                self.model = genai.GenerativeModel('gemini-1.5-flash')
            except Exception as e:
                st.error(f"❌ Error initializing Gemini model: {str(e)}")
                self.model = None
        else:
            self.model = None
    
    def extract_text_from_pdf(self, uploaded_file) -> str:
        """Extract text from uploaded PDF using pdfplumber"""
        try:
            import pdfplumber
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_file_path = tmp_file.name
            
            text = ""
            with pdfplumber.open(tmp_file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            
            os.unlink(tmp_file_path)  # Clean up temp file
            return text.strip()
        
        except ImportError:
            st.error("📦 pdfplumber not installed. Please install: pip install pdfplumber")
            return ""
        except Exception as e:
            st.error(f"❌ Error extracting PDF text: {str(e)}")
            return ""
    
    def extract_text_from_docx(self, uploaded_file) -> str:
        """Extract text from uploaded DOCX using docx2txt"""
        try:
            import docx2txt
            with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_file_path = tmp_file.name
            
            text = docx2txt.process(tmp_file_path)
            os.unlink(tmp_file_path)  # Clean up temp file
            return text.strip() if text else ""
        
        except ImportError:
            st.error("📦 docx2txt not installed. Please install: pip install docx2txt")
            return ""
        except Exception as e:
            st.error(f"❌ Error extracting DOCX text: {str(e)}")
            return ""
    
    def safe_join_list(self, data, separator=', ') -> str:
        """Safely join list data, handling nested lists and non-string items"""
        if not data:
            return ""
        
        # Convert to list if it's not already
        if not isinstance(data, list):
            return str(data)
        
        # Flatten and stringify all items
        flattened = []
        for item in data:
            if isinstance(item, list):
                # If item is a list, recursively flatten it
                flattened.extend([str(x) for x in item])
            else:
                flattened.append(str(item))
        
        return separator.join(flattened)
    
    def parse_with_gemini(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse job description using Gemini AI to extract structured data"""
        if not self.model:
            st.error("❌ Gemini AI model not available")
            return None
            
        try:
            prompt = f"""
            Analyze the following job description and extract structured information in JSON format. 
            
            Please extract:
            1. job_title: The main job title/position (string)
            2. company_name: Company or organization name (string)
            3. location: Job location (string)
            4. job_description: Complete job description text (string)
            5. required_skills: List of required skills (array of strings)
            6. optional_skills: List of preferred skills (array of strings)
            7. experience_required: Years of experience required (string)
            8. education_requirements: Education requirements (string)
            9. employment_type: Full-time, Part-time, Contract, etc. (string)
            10. salary_range: Salary information if mentioned (string)
            11. benefits: List of benefits mentioned (array of strings)
            12. responsibilities: List of key responsibilities (array of strings)
            13. department: Department or team (string)
            14. posted_by: Person or department posting the job (string)
            
            IMPORTANT: 
            - Return ONLY valid JSON
            - All arrays should contain only strings, no nested arrays
            - Use empty string "" for missing string fields
            - Use empty array [] for missing array fields
            - Do not include any explanatory text
            
            Job Description Text:
            {text}
            """
            
            response = self.model.generate_content(prompt)
            
            # Clean and parse the JSON response
            json_text = response.text.strip()
            
            # Remove any markdown formatting if present
            if json_text.startswith("```json"):
                json_text = json_text[7:]
            if json_text.endswith("```"):
                json_text = json_text[:-3]
            
            json_text = json_text.strip()
            
            parsed_data = json.loads(json_text)
            
            # Validate and clean the parsed data
            cleaned_data = self.validate_parsed_data(parsed_data)
            return cleaned_data
            
        except json.JSONDecodeError as e:
            st.error(f"❌ Error parsing Gemini response as JSON: {str(e)}")
            st.error(f"Raw response: {response.text[:500]}...")
            return None
        except Exception as e:
            st.error(f"❌ Error with Gemini AI parsing: {str(e)}")
            return None
    
    def validate_parsed_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean parsed data to ensure correct types"""
        cleaned = {}
        
        # String fields
        string_fields = ['job_title', 'company_name', 'location', 'job_description', 
                        'experience_required', 'education_requirements', 'employment_type', 
                        'salary_range', 'department', 'posted_by']
        
        for field in string_fields:
            value = data.get(field, "")
            cleaned[field] = str(value) if value else ""
        
        # Array fields
        array_fields = ['required_skills', 'optional_skills', 'benefits', 'responsibilities']
        
        for field in array_fields:
            value = data.get(field, [])
            if isinstance(value, list):
                # Flatten any nested lists and convert to strings
                flattened = []
                for item in value:
                    if isinstance(item, list):
                        flattened.extend([str(x) for x in item])
                    else:
                        flattened.append(str(item))
                cleaned[field] = flattened
            else:
                cleaned[field] = [str(value)] if value else []
        
        return cleaned

def display():
    st.markdown("<h2 style='color:#0b5fff; margin-bottom: 2rem;'>Create Job Posting</h2>", unsafe_allow_html=True)
    
    # Authentication check
    if not st.session_state.get("api_key"):
        st.error("🔒 This page is for employees/recruiters. Please login from top-right.")
        st.stop()

    # Initialize parser
    parser = JobDescriptionParser() if GEMINI_API_KEY else None
    
    # Tabs for different input methods
    tab1, tab2 = st.tabs(["📝 Manual Entry", "📄 Upload Document"])
    
    with tab1:
        display_manual_entry()
    
    with tab2:
        if parser and parser.model:
            display_document_upload(parser)
        else:
            st.error("🔧 Gemini AI not configured. Please set GEMINI_API_KEY in environment variables.")

def display_manual_entry():
    """Display manual job creation form"""
    st.markdown("### Manual Job Creation")
    st.markdown("Fill out the form below to create a new job posting manually.")
    
    with st.form("manual_job_creation_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            job_title = st.text_input("Job Title *", placeholder="e.g., Senior Python Developer")
            # Use ss_get_nested to avoid AttributeError when recruiter_info is None
            company_name = st.text_input(
                "Company Name *", 
                value=ss_get_nested("recruiter_info", "company", ""),
                placeholder="e.g., Tech Solutions Inc."
            )
            location = st.text_input("Location *", placeholder="e.g., New York, NY / Remote")
            posted_by = st.text_input(
                "Posted By (Your Name) *", 
                value=ss_get_nested("recruiter_info", "name", ""),
                placeholder="e.g., John Smith"
            )
        
        with col2:
            employment_type = st.selectbox(
                "Employment Type",
                options=["Full-time", "Part-time", "Contract", "Internship", "Remote"],
                index=0
            )
            experience_required = st.text_input(
                "Experience Required", 
                placeholder="e.g., 2-4 years"
            )
            salary_range = st.text_input(
                "Salary Range (Optional)", 
                placeholder="e.g., $70,000 - $90,000"
            )
            department = st.text_input(
                "Department", 
                placeholder="e.g., Engineering"
            )
        
        job_description = st.text_area(
            "Job Description *", 
            height=300,
            placeholder="Enter detailed job description including responsibilities, requirements, and benefits..."
        )
        
        # Submit button
        submit_manual = st.form_submit_button("🚀 Create Job", type="primary", use_container_width=True)
        
        if submit_manual:
            if not all([job_title, company_name, location, posted_by, job_description]):
                st.error("❌ All required fields (*) must be filled")
            else:
                create_job_with_data({
                    'job_title': job_title,
                    'company_name': company_name,
                    'location': location,
                    'posted_by': posted_by,
                    'job_description': job_description,
                    'employment_type': employment_type,
                    'experience_required': experience_required,
                    'salary_range': salary_range,
                    'department': department
                })


def display_document_upload(parser: JobDescriptionParser):
    """Display document upload and AI parsing interface"""
    st.markdown("### Upload Job Description Document")
    st.markdown("Upload a PDF or DOCX file containing the job description. Our AI will extract and structure the information automatically.")
    
    # File uploader
    uploaded_file = st.file_uploader(
        "📁 Choose a file",
        type=['pdf', 'docx', 'doc'],
        help="Upload PDF or DOCX files containing job descriptions"
    )
    
    if uploaded_file is not None:
        # Display file info
        file_details = {
            "Filename": uploaded_file.name,
            "File size": f"{uploaded_file.size / 1024:.2f} KB",
            "File type": uploaded_file.type
        }
        
        with st.expander("📋 File Details", expanded=False):
            for key, value in file_details.items():
                st.text(f"{key}: {value}")
        
        # Extract and parse button
        col1, col2 = st.columns([1, 1])
        
        with col1:
            parse_button = st.button(
                "🤖 Extract & Parse with AI", 
                type="primary", 
                use_container_width=True,
                help="Use AI to extract job information from the uploaded document"
            )
        
        with col2:
            preview_button = st.button(
                "👁️ Preview Text Only", 
                use_container_width=True,
                help="Show raw extracted text without AI parsing"
            )
        
        # Process the file
        if parse_button or preview_button:
            with st.spinner("🔄 Processing document..."):
                # Extract text based on file type
                if uploaded_file.type == "application/pdf":
                    extracted_text = parser.extract_text_from_pdf(uploaded_file)
                elif uploaded_file.type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword"]:
                    extracted_text = parser.extract_text_from_docx(uploaded_file)
                else:
                    st.error("❌ Unsupported file type")
                    return
                
                if not extracted_text:
                    st.error("❌ Could not extract text from the document")
                    return
                
                # Show preview if requested
                if preview_button:
                    st.markdown("### 📄 Extracted Text Preview")
                    with st.expander("Raw Text Content", expanded=True):
                        st.text_area("", value=extracted_text, height=300, disabled=True)
                    return
                
                # Parse with AI if requested
                if parse_button:
                    with st.spinner("🧠 Analyzing with Gemini AI..."):
                        parsed_data = parser.parse_with_gemini(extracted_text)
                        
                        if parsed_data:
                            st.success("✅ Document successfully parsed!")
                            display_parsed_job_form(parsed_data, extracted_text, parser)
                        else:
                            st.error("❌ Failed to parse document with AI")
                            # Fallback: show raw text
                            st.markdown("### 📝 Manual Entry Required")
                            st.info("AI parsing failed. Please use the manual entry tab or check the document format.")

def display_parsed_job_form(parsed_data: Dict[str, Any], original_text: str, parser: JobDescriptionParser):
    """Display form with AI-parsed data for review and editing"""
    st.markdown("### 🎯 AI-Parsed Job Information")
    st.info("📝 Review and edit the AI-extracted information below before creating the job posting.")
    
    with st.form("ai_parsed_job_form"):
        # Create expandable sections for better organization
        with st.expander("🏢 Basic Information", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                job_title = st.text_input(
                    "Job Title *", 
                    value=parsed_data.get('job_title', ''),
                    help="AI-extracted job title"
                )
                company_name = st.text_input(
                    "Company Name *", 
                    value=ss_get_nested("recruiter_info", "company", ""),
                    placeholder="e.g., Tech Solutions Inc."
                )

                location = st.text_input(
                    "Location *", 
                    value=parsed_data.get('location', ''),
                    help="AI-extracted job location"
                )
            
            with col2:
                posted_by = st.text_input(
                    "Posted By (Your Name) *", 
                    value=ss_get_nested("recruiter_info", "name", ""),
                    placeholder="e.g., John Smith"
                )
                employment_type = st.text_input(
                    "Employment Type", 
                    value=parsed_data.get('employment_type', ''),
                    help="AI-extracted employment type"
                )
                department = st.text_input(
                    "Department", 
                    value=parsed_data.get('department', ''),
                    help="AI-extracted department"
                )
        
        with st.expander("💼 Job Details", expanded=True):
            job_description = st.text_area(
                "Job Description *", 
                value=parsed_data.get('job_description', original_text),
                height=200,
                help="AI-processed job description"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                experience_required = st.text_input(
                    "Experience Required", 
                    value=parsed_data.get('experience_required', ''),
                    help="AI-extracted experience requirements"
                )
                salary_range = st.text_input(
                    "Salary Range", 
                    value=parsed_data.get('salary_range', ''),
                    help="AI-extracted salary information"
                )
            
            with col2:
                education_requirements = st.text_area(
                    "Education Requirements", 
                    value=str(parsed_data.get('education_requirements', '')),
                    height=80,
                    help="AI-extracted education requirements"
                )
        
        with st.expander("🔧 Skills & Requirements", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                # FIXED: Use safe_join_list method
                required_skills = st.text_area(
                    "Required Skills", 
                    value=parser.safe_join_list(parsed_data.get('required_skills', [])),
                    height=100,
                    help="AI-extracted required skills (comma-separated)"
                )
            
            with col2:
                # FIXED: Use safe_join_list method
                optional_skills = st.text_area(
                    "Optional/Preferred Skills", 
                    value=parser.safe_join_list(parsed_data.get('optional_skills', [])),
                    height=100,
                    help="AI-extracted optional skills (comma-separated)"
                )
            
            # FIXED: Handle responsibilities list properly
            responsibilities_list = parsed_data.get('responsibilities', [])
            responsibilities_text = ""
            if responsibilities_list:
                if isinstance(responsibilities_list, list):
                    responsibilities_text = '\n'.join([f"• {str(resp)}" for resp in responsibilities_list])
                else:
                    responsibilities_text = str(responsibilities_list)
            
            responsibilities = st.text_area(
                "Key Responsibilities", 
                value=responsibilities_text,
                height=120,
                help="AI-extracted key responsibilities"
            )
        
        with st.expander("🎁 Benefits & Additional Info", expanded=False):
            # FIXED: Handle benefits list properly
            benefits_list = parsed_data.get('benefits', [])
            benefits_text = ""
            if benefits_list:
                if isinstance(benefits_list, list):
                    benefits_text = '\n'.join([f"• {str(benefit)}" for benefit in benefits_list])
                else:
                    benefits_text = str(benefits_list)
            
            benefits = st.text_area(
                "Benefits", 
                value=benefits_text,
                height=100,
                help="AI-extracted benefits"
            )
        
        # Action buttons
        col1, col2 = st.columns([1, 1])
        
        with col1:
            create_button = st.form_submit_button("🚀 Create Job", type="primary", use_container_width=True)
        
        with col2:
            # Preview button to show structured data
            preview_button = st.form_submit_button("👁️ Preview Data", use_container_width=True)
        
        # Handle form submission
        if create_button:
            if not all([job_title, company_name, location, posted_by, job_description]):
                st.error("❌ All required fields (*) must be filled")
            else:
                job_data = {
                    'job_title': job_title,
                    'company_name': company_name,
                    'location': location,
                    'posted_by': posted_by,
                    'job_description': job_description,
                    'employment_type': employment_type,
                    'experience_required': experience_required,
                    'salary_range': salary_range,
                    'department': department,
                    'education_requirements': education_requirements,
                    'required_skills': required_skills,
                    'optional_skills': optional_skills,
                    'responsibilities': responsibilities,
                    'benefits': benefits
                }
                create_job_with_data(job_data, uploaded_file=uploaded_file)

        
        if preview_button:
            st.json(parsed_data)

def create_job_with_data(job_data: Dict[str, Any], uploaded_file=None):
    """Create job with the provided data. If uploaded_file provided, send file to backend."""
    import requests
    from frontend.ui.utils import API_BASE_URL  # adjust if your utils exposes base url

    with st.spinner("🔄 Creating job..."):
        try:
            url = f"{API_BASE_URL}/upload-job"
            # Prepare payload
            payload = {
                "job_title": job_data.get("job_title", ""),
                "company_name": job_data.get("company_name", ""),
                "location": job_data.get("location", ""),
                "posted_by": job_data.get("posted_by", "")
            }

            if uploaded_file:
                # upload file as multipart
                files = {
                    "file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)
                }
                resp = requests.post(url, data=payload, files=files, timeout=60)
            else:
                # send job_text in body
                payload["job_text"] = job_data.get("job_description", "")
                resp = requests.post(url, json=payload, timeout=60)

            if resp is None:
                st.error("❌ No response from server.")
                return

            if resp.status_code in (200, 201):
                try:
                    body = resp.json()
                except Exception:
                    body = {"status": "ok", "message": resp.text}
                if body.get("status") == "ok":
                    st.success("✅ Job created successfully!")
                    created = body.get("job") or {}
                    with st.expander("📋 Created Job Summary", expanded=True):
                        st.markdown(f"**Job Title:** {created.get('job_title', job_data.get('job_title'))}")
                        st.markdown(f"**Company:** {created.get('company_name', job_data.get('company_name'))}")
                        st.markdown(f"**Location:** {created.get('location', job_data.get('location'))}")
                        st.markdown(f"**Posted By:** {created.get('posted_by', job_data.get('posted_by'))}")
                        if created.get('employment_type'):
                            st.markdown(f"**Employment Type:** {created.get('employment_type')}")
                        if created.get('min_experience'):
                            st.markdown(f"**Experience Required:** {created.get('min_experience')}")
                        if created.get('salary_range'):
                            st.markdown(f"**Salary Range:** {created.get('salary_range')}")
                    if st.button("➕ Create Another Job"):
                        st.rerun()
                else:
                    st.error(f"❌ Failed to create job: {body.get('message', 'unknown error')}")
            else:
                st.error(f"❌ Failed to create job. Status: {resp.status_code} - {resp.text}")
        except Exception as e:
            st.error(f"❌ Error creating job: {str(e)}")
