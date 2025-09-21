# frontend/ui/styles.py
import streamlit as st

def load_css():
    st.markdown(
        """
        <style>
        /* App background */
        .stApp {
            background: linear-gradient(180deg, #0f172a 0%, #111827 60%, #0b1220 100%);
            color: #e5e7eb;
        }
        /* Section containers as cards */
        .card {
            background: #0b1220cc;
            border: 1px solid #1f2937;
            border-radius: 14px;
            padding: 18px 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.35);
            margin-bottom: 14px;
        }
        .card h3 {
            margin-top: 0;
            color: #e5e7eb;
        }
        /* Buttons */
        .stButton>button {
            background: #2563eb !important;
            color: #fff !important;
            border-radius: 10px !important;
            border: none !important;
            padding: 0.6rem 1rem !important;
        }
        .stButton>button:hover {
            background: #1d4ed8 !important;
            transform: translateY(-1px);
        }
        /* Inputs */
        .stTextInput>div>div>input, .stSelectbox>div>div>div>div {
            background: #0f172a !important;
            color: #e5e7eb !important;
            border-radius: 10px !important;
            border: 1px solid #1f2937 !important;
        }
        /* Tags */
        .tag {
            display: inline-block;
            background: #111827;
            border: 1px solid #1f2937;
            color: #9ca3af;
            padding: 3px 10px;
            margin: 2px 6px 6px 0;
            border-radius: 9999px;
            font-size: 12px;
        }
        /* Header band */
        .header-band {
            background: radial-gradient(1200px 300px at 25% -30%, rgba(37,99,235,0.35), rgba(0,0,0,0) 70%);
            padding: 6px 0 14px 0;
            border-bottom: 1px solid #1f2937;
        }
        /* Subtle separators */
        hr { border-color: #1f2937; }
        </style>
        """,
        unsafe_allow_html=True,
    )
