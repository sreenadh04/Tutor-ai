"""
MediTutor AI - Page 2: Q&A Chat
"""

import sys
from pathlib import Path

import requests
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from common import ensure_study_session, get_api_headers, get_api_url

st.set_page_config(page_title="Q&A - MediTutor AI", page_icon="💬", layout="wide")

API_URL = get_api_url()
doc_id = st.session_state.get("selected_doc_id")
doc_name = st.session_state.get("selected_doc_name", "Unknown")

st.title("💬 Ask Questions")
st.caption("RAG-powered Q&A with source citations from your document.")

if not doc_id:
    st.warning("Please select a document first.")
    st.stop()

st.info(f"📄 Active document: **{doc_name}**")
try:
    ensure_study_session(doc_id, API_URL)
except Exception:
    pass

st.session_state.setdefault("chat_history", [])
for message in st.session_state["chat_history"]:
    if message["role"] == "user":
        st.chat_message("user").write(message["content"])
    else:
        with st.chat_message("assistant"):
            st.write(message["content"])
            for source in message.get("sources", []):
                st.caption(f"Page {source.get('page_number', '?')} | score {source.get('relevance_score', 0):.2f}")
                st.code(source["text"])
            if message.get("model_used"):
                st.caption(f"Model: `{message['model_used']}`")

question = st.chat_input("Ask a question about your document...")
if question:
    st.session_state["chat_history"].append({"role": "user", "content": question})
    with st.spinner("Searching and generating answer..."):
        try:
            response = requests.post(
                f"{API_URL}/qa/ask",
                json={
                    "document_id": doc_id,
                    "question": question,
                    "session_id": st.session_state.get("session_id"),
                },
                headers=get_api_headers(),
                timeout=90,
            )
            if response.ok:
                data = response.json()
                st.session_state["chat_history"].append(
                    {
                        "role": "assistant",
                        "content": data["answer"],
                        "sources": data.get("sources", []),
                        "model_used": data.get("model_used", ""),
                    }
                )
                st.rerun()
            else:
                st.error(response.json().get("detail", "Failed to get answer."))
        except Exception as exc:
            st.error(f"Error: {exc}")

if st.session_state["chat_history"] and st.button("🗑️ Clear Chat History"):
    st.session_state["chat_history"] = []
    st.rerun()
