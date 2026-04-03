"""
MediTutor AI - Streamlit Frontend
Main entry point with per-session user isolation.
"""

import requests
import streamlit as st

from common import ensure_study_session, get_api_headers, get_api_url, get_backend_base, get_or_create_user_id

st.set_page_config(
    page_title="MediTutor AI",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_URL = get_api_url()

defaults = {
    "api_url": API_URL,
    "selected_doc_id": None,
    "selected_doc_name": None,
    "session_id": None,
    "session_doc_id": None,
    "chat_history": [],
    "current_mcqs": [],
    "current_flashcards": [],
    "mcq_answers": {},
    "quiz_submitted": False,
    "flashcard_index": 0,
    "show_answer": False,
}

user_id = get_or_create_user_id()
for key, value in defaults.items():
    st.session_state.setdefault(key, value)

st.markdown(
    """
<style>
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%); }
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
.hero { background: linear-gradient(135deg, #0f172a 0%, #312e81 50%, #0f172a 100%); color:white; padding:2rem; border-radius:16px; margin-bottom:1.5rem; }
.hero p { color:#a5b4fc; }
.mt-card-blue, .mt-card-green, .mt-card-yellow { border-radius:12px; padding:1.2rem 1.5rem; }
.mt-card-blue { background: linear-gradient(135deg, #eff6ff, #dbeafe); }
.mt-card-green { background: linear-gradient(135deg, #f0fdf4, #dcfce7); }
.mt-card-yellow { background: linear-gradient(135deg, #fffbeb, #fef3c7); }
.user-badge { background:#334155; border-radius:8px; padding:0.3rem 0.6rem; font-size:0.7rem; font-family:monospace; color:#94a3b8; text-align:center; }
</style>
""",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("## 🧠 MediTutor AI")
    st.markdown(
        f'<div class="user-badge">User: {user_id[:8]}...{user_id[-4:]}</div>',
        unsafe_allow_html=True,
    )
    st.markdown("---")

    try:
        response = requests.get(f"{st.session_state.api_url}/pdf/list", headers=get_api_headers(), timeout=5)
        docs = response.json().get("documents", []) if response.ok else []
    except Exception as exc:
        docs = []
        st.warning(f"Backend offline: {str(exc)[:50]}")

    if docs:
        doc_options = {f"📄 {doc['filename'][:30]}": doc for doc in docs}
        selected_label = st.selectbox("Active Document", list(doc_options.keys()), index=0)
        selected_doc = doc_options[selected_label]
        st.session_state["selected_doc_id"] = selected_doc["id"]
        st.session_state["selected_doc_name"] = selected_doc["filename"]
        st.caption(f"{selected_doc['total_pages']} pages | {selected_doc['total_chunks']} chunks")
    else:
        st.info("Upload a PDF to get started.")
        st.session_state["selected_doc_id"] = None
        st.session_state["selected_doc_name"] = None

    st.markdown("---")
    st.page_link("app.py", label="🏠 Home")
    st.page_link("pages/1_Upload.py", label="📤 Upload PDF")
    st.page_link("pages/2_QA_Chat.py", label="💬 Ask Questions")
    st.page_link("pages/3_Flashcards.py", label="🃏 Flashcards")
    st.page_link("pages/4_MCQ_Quiz.py", label="📝 MCQ Quiz")
    st.page_link("pages/5_Progress.py", label="📊 Progress")
    st.page_link("pages/6_Prereq.py", label="🔍 Prerequisites")
    st.markdown("---")

    if st.button("🗑️ Clear My Data", use_container_width=True):
        try:
            response = requests.delete(
                f"{get_backend_base()}/api/v1/user/data",
                headers=get_api_headers(),
                timeout=30,
            )
            if response.ok:
                st.session_state.clear()
                st.success("Your data has been deleted.")
                st.rerun()
            else:
                st.error(response.json().get("detail", "Failed to delete data."))
        except Exception as exc:
            st.error(f"Error deleting user data: {exc}")

if st.session_state.get("selected_doc_id"):
    try:
        ensure_study_session(st.session_state["selected_doc_id"], API_URL)
    except Exception:
        st.warning("Could not start a study session. Progress tracking may be delayed.")

st.markdown(
    """
<div class="hero">
  <h1>🧠 MediTutor AI</h1>
  <p>Your AI-powered study assistant. Upload a textbook, ask grounded questions, and study with generated flashcards and quizzes.</p>
</div>
""",
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown('<div class="mt-card-blue"><h3>📤 Upload PDF</h3><p>Index your study material locally with user-isolated storage.</p></div>', unsafe_allow_html=True)
with col2:
    st.markdown('<div class="mt-card-green"><h3>💬 Ask Questions</h3><p>RAG-powered answers with source citations from your own document.</p></div>', unsafe_allow_html=True)
with col3:
    st.markdown('<div class="mt-card-yellow"><h3>🃏 Flashcards + MCQs</h3><p>Generate revision content and track progress topic by topic.</p></div>', unsafe_allow_html=True)

st.markdown("### Quick Start")
st.markdown(
    """
1. Upload a PDF from the sidebar.
2. Select the active document.
3. Ask questions, generate flashcards, or start a quiz.
4. Review progress and prerequisite gaps.
"""
)

st.markdown("### System Status")
left, right = st.columns(2)
with left:
    try:
        response = requests.get(f"{get_backend_base()}/health", headers=get_api_headers(), timeout=4)
        if response.ok:
            health = response.json()
            st.success("Backend connected")
            st.write(f"Groq configured: `{health.get('llm', {}).get('groq', {}).get('configured', False)}`")
            st.write(f"HuggingFace configured: `{health.get('llm', {}).get('huggingface', {}).get('configured', False)}`")
            st.write(f"Auth mode: `{health.get('auth', {}).get('mode', 'unknown')}`")
        else:
            st.error("Backend returned an error")
    except Exception as exc:
        st.error(f"Backend not reachable: {str(exc)[:50]}")
with right:
    st.info(f"API URL: `{st.session_state.api_url}`\n\nUser ID: `{user_id}`")
