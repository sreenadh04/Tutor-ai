"""
MediTutor AI - Page 6: Prerequisite Checker
"""

import sys
from pathlib import Path

import requests
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from common import get_api_headers, get_api_url

st.set_page_config(page_title="Prerequisites - MediTutor AI", page_icon="🔍", layout="wide")

API_URL = get_api_url()
doc_id = st.session_state.get("selected_doc_id")
doc_name = st.session_state.get("selected_doc_name", "")

st.title("🔍 Prerequisite Checker")
st.caption("Find prerequisite concepts before tackling a difficult topic.")

if not doc_id:
    st.warning("Please select a document first.")
    st.stop()

st.info(f"📄 Document: **{doc_name}**")

query = st.text_area("What topic are you about to study?", height=120)
if st.button("Check Prerequisites", type="primary", use_container_width=True) and query.strip():
    with st.spinner("Analyzing prerequisites..."):
        try:
            response = requests.post(
                f"{API_URL}/prereq/check",
                json={"document_id": doc_id, "query": query.strip()},
                headers=get_api_headers(),
                timeout=60,
            )
            if response.ok:
                data = response.json()
                st.success(f"Analysis complete - `{data.get('model_used', 'AI')}`")
                st.subheader("Missing Concepts")
                for item in data.get("missing_concepts", []):
                    st.write(f"- {item}")
                st.subheader("Prerequisite Topics")
                prereqs = data.get("prerequisite_topics", [])
                for item in prereqs:
                    st.write(f"- {item}")
                st.subheader("Study Recommendations")
                for item in data.get("study_recommendations", []):
                    st.write(f"- {item}")
                weak_related = data.get("weak_related_topics", [])
                if weak_related:
                    st.subheader("Weak Related Topics")
                    for item in weak_related:
                        st.write(f"- {item}")
                if prereqs:
                    if st.button("Use first prerequisite for flashcards", use_container_width=True):
                        st.session_state["prereq_topic"] = prereqs[0]
                        st.switch_page("pages/3_Flashcards.py")
                    if st.button("Use first prerequisite for quiz", use_container_width=True):
                        st.session_state["prereq_topic"] = prereqs[0]
                        st.switch_page("pages/4_MCQ_Quiz.py")
            else:
                st.error(response.json().get("detail", "Prerequisite check failed."))
        except Exception as exc:
            st.error(str(exc))
