"""
MediTutor AI - Page 5: Progress Dashboard
"""

import sys
from pathlib import Path

import requests
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from common import get_api_headers, get_api_url

st.set_page_config(page_title="Progress - MediTutor AI", page_icon="📊", layout="wide")

API_URL = get_api_url()
doc_id = st.session_state.get("selected_doc_id")
doc_name = st.session_state.get("selected_doc_name", "")

st.title("📊 Progress Dashboard")
st.caption("Track performance and weak topics for the selected document.")

if not doc_id:
    st.warning("Please select a document first.")
    st.stop()

st.info(f"📄 Document: **{doc_name}**")

try:
    response = requests.get(f"{API_URL}/progress/{doc_id}", headers=get_api_headers(), timeout=10)
    if not response.ok:
        st.error(response.json().get("detail", "Failed to load progress."))
        st.stop()
    progress = response.json()
except Exception as exc:
    st.error(f"Backend error: {exc}")
    st.stop()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Attempts", progress["total_attempts"])
col2.metric("Correct", progress["total_correct"])
col3.metric("Accuracy", f"{progress['overall_accuracy']:.1f}%")
col4.metric("Weak Topics", len(progress["weak_topics"]))

st.subheader("Weak Topics")
if progress["weak_topics"]:
    for topic in progress["weak_topics"]:
        st.write(f"- {topic}")
else:
    st.success("No weak topics yet.")

st.subheader("Strong Topics")
if progress["strong_topics"]:
    for topic in progress["strong_topics"]:
        st.write(f"- {topic}")
else:
    st.info("No strong topics yet.")

st.subheader("Topic Breakdown")
if progress["topics"]:
    st.dataframe(progress["topics"], use_container_width=True)
else:
    st.info("No topic data yet.")

st.subheader("Recent Sessions")
if progress["recent_sessions"]:
    st.dataframe(progress["recent_sessions"], use_container_width=True)
else:
    st.info("No recent sessions yet.")
