"""
MediTutor AI - Page 1: Upload PDF
"""

import sys
from pathlib import Path

import requests
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from common import get_api_headers, get_api_url, get_or_create_user_id, get_upload_headers

st.set_page_config(page_title="Upload PDF - MediTutor AI", page_icon="📤", layout="wide")

API_URL = get_api_url()
user_id = get_or_create_user_id()

st.title("📤 Upload PDF")
st.caption("Upload any textbook or study material. Supported: text-based PDFs.")
st.markdown(f"`User ID:` `{user_id}`")
st.markdown("---")

uploaded = st.file_uploader("Choose a PDF file", type=["pdf"], accept_multiple_files=False)
if uploaded:
    st.markdown(f"**Selected:** `{uploaded.name}` - {uploaded.size / 1024:.1f} KB")
    if st.button("🚀 Process & Index PDF", type="primary", use_container_width=True):
        with st.spinner("Reading PDF and building vector index..."):
            try:
                response = requests.post(
                    f"{API_URL}/pdf/upload",
                    files={"file": (uploaded.name, uploaded.getvalue(), "application/pdf")},
                    headers=get_upload_headers(),
                    timeout=120,
                )
                if response.ok:
                    document = response.json()
                    st.success(f"Processed `{document['filename']}`")
                    st.session_state["selected_doc_id"] = document["id"]
                    st.session_state["selected_doc_name"] = document["filename"]
                else:
                    st.error(response.json().get("detail", "Upload failed."))
            except requests.exceptions.Timeout:
                st.error("The upload timed out. Try a smaller PDF.")
            except Exception as exc:
                st.error(str(exc))

st.divider()
st.subheader("📚 Your Uploaded Documents")

try:
    response = requests.get(f"{API_URL}/pdf/list", headers=get_api_headers(), timeout=10)
    documents = response.json().get("documents", []) if response.ok else []
    if not documents:
        st.info("No documents uploaded yet.")
    else:
        for document in documents:
            col1, col2, col3, col4 = st.columns([4, 1, 1, 1])
            col1.markdown(f"**{document['filename']}**")
            col1.caption(f"{document['total_pages']} pages | {document['total_chunks']} chunks")
            if col2.button("Select", key=f"select_{document['id']}", use_container_width=True):
                st.session_state["selected_doc_id"] = document["id"]
                st.session_state["selected_doc_name"] = document["filename"]
                st.rerun()
            if col3.button("Delete", key=f"delete_{document['id']}", use_container_width=True):
                delete_response = requests.delete(
                    f"{API_URL}/pdf/{document['id']}",
                    headers=get_api_headers(),
                    timeout=30,
                )
                if delete_response.ok:
                    if st.session_state.get("selected_doc_id") == document["id"]:
                        st.session_state["selected_doc_id"] = None
                        st.session_state["selected_doc_name"] = None
                    st.rerun()
                else:
                    st.error(delete_response.json().get("detail", "Delete failed."))
            col4.markdown(f"`{document['id'][:8]}...`")
            st.divider()
except Exception as exc:
    st.error(f"Could not fetch document list: {exc}")
