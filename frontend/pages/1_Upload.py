"""
MediTutor AI — Page 1: Upload PDF
"""

import streamlit as st
import requests
import os

st.set_page_config(page_title="Upload PDF — MediTutor AI", page_icon="📤", layout="wide")

BASE_BACKEND = os.getenv(
    "BACKEND_URL",
    "https://meditutor-backend-v2.onrender.com"
)

API_URL = f"{BASE_BACKEND}/api/v1"

# ── Shared CSS snippet (minimal, main CSS is in app.py) ──────────────────────
st.markdown("""
<style>
.upload-zone { border: 2px dashed #6366f1; border-radius: 12px; padding: 2rem; text-align: center; background: #fafafa; }
.doc-row { display: flex; justify-content: space-between; align-items: center;
           padding: 0.8rem 1rem; border: 1px solid #e2e8f0; border-radius: 8px;
           margin-bottom: 0.5rem; background: white; }
</style>
""", unsafe_allow_html=True)

st.title("📤 Upload PDF")
st.caption("Upload any textbook or study material. Supported: text-based PDFs (not scanned images).")

# ── Upload Section ────────────────────────────────────────────────────────────
uploaded = st.file_uploader(
    "Choose a PDF file",
    type=["pdf"],
    accept_multiple_files=False,
    help="Max 50 MB. Must be a text-based PDF (not a scanned image).",
)

if uploaded:
    st.markdown(f"**Selected:** `{uploaded.name}` — {uploaded.size / 1024:.1f} KB")
    
    if st.button("🚀 Process & Index PDF", type="primary", use_container_width=True):
        with st.spinner("📖 Reading PDF... extracting text... building vector index..."):
            try:
                files = {"file": (uploaded.name, uploaded.getvalue(), "application/pdf")}
                resp = requests.post(f"{API_URL}/pdf/upload", files=files, timeout=120)
                
                if resp.status_code == 200:
                    doc = resp.json()
                    st.success(f"✅ Successfully processed **{doc['filename']}**")
                    
                    col1, col2, col3 = st.columns(3)
                    col1.metric("📑 Pages", doc["total_pages"])
                    col2.metric("🧩 Chunks", doc["total_chunks"])
                    col3.metric("🆔 Doc ID", doc["id"][:8] + "...")
                    
                    st.info("👈 Select this document from the sidebar to start studying!")
                    st.session_state["selected_doc_id"] = doc["id"]
                    st.session_state["selected_doc_name"] = doc["filename"]
                    
                elif resp.status_code == 422:
                    st.error("❌ Could not extract text. This PDF may be image-only (scanned). Try a text-based PDF.")
                elif resp.status_code == 413:
                    st.error("❌ File too large. Maximum size is 50 MB.")
                else:
                    st.error(f"❌ Upload failed: {resp.json().get('detail', 'Unknown error')}")
                    
            except requests.exceptions.ConnectionError:
                st.error("❌ Cannot connect to backend. Make sure the FastAPI server is running.")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

st.divider()

# ── Existing Documents ────────────────────────────────────────────────────────
st.subheader("📚 Uploaded Documents")

try:
    resp = requests.get(f"{API_URL}/pdf/list", timeout=5)
    if resp.ok:
        docs = resp.json().get("documents", [])
        
        if not docs:
            st.info("No documents uploaded yet. Upload your first PDF above.")
        else:
            for doc in docs:
                with st.container():
                    col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
                    with col1:
                        st.markdown(f"**📄 {doc['filename']}**")
                        st.caption(f"ID: {doc['id'][:16]}...")
                    with col2:
                        st.markdown(f"**{doc['total_pages']}** pages")
                    with col3:
                        st.markdown(f"**{doc['total_chunks']}** chunks")
                    with col4:
                        if st.button("Select", key=f"sel_{doc['id']}", use_container_width=True):
                            st.session_state["selected_doc_id"] = doc["id"]
                            st.session_state["selected_doc_name"] = doc["filename"]
                            st.success(f"Selected: {doc['filename']}")
                    with col5:
                        if st.button("🗑️ Delete", key=f"del_{doc['id']}", use_container_width=True):
                            del_resp = requests.delete(f"{API_URL}/pdf/{doc['id']}", timeout=10)
                            if del_resp.ok:
                                st.success("Deleted!")
                                st.rerun()
                    st.divider()
    else:
        st.warning("Could not fetch document list.")
except Exception as e:
    st.error(f"Backend error: {e}")

# ── Tips ──────────────────────────────────────────────────────────────────────
with st.expander("💡 Tips for best results"):
    st.markdown("""
    - **Text-based PDFs work best** — PDFs where you can select/copy text
    - **Avoid scanned PDFs** — These contain images of text, not actual text
    - **Large PDFs (200+ pages)** — Take 1-2 minutes to process; please wait
    - **Multiple PDFs** — Upload as many as you need; switch via the sidebar
    - **Re-upload** — If a document seems broken, delete and re-upload it
    """)
