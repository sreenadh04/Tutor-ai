"""
MediTutor AI - Page 3: Flashcards
"""

import sys
from pathlib import Path

import requests
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from common import get_api_headers, get_api_url

st.set_page_config(page_title="Flashcards - MediTutor AI", page_icon="🃏", layout="wide")

API_URL = get_api_url()
doc_id = st.session_state.get("selected_doc_id")
doc_name = st.session_state.get("selected_doc_name", "")

st.title("🃏 Flashcards")
st.caption("Generate flashcards from the selected document.")

if not doc_id:
    st.warning("Please select a document first.")
    st.stop()

st.info(f"📄 Document: **{doc_name}**")

topic_default = st.session_state.pop("prereq_topic", "")
topic = st.text_input("Topic (optional)", value=topic_default)
count = st.slider("Number of flashcards", 5, 30, 10)

if st.button("✨ Generate Flashcards", type="primary", use_container_width=True):
    with st.spinner("Generating flashcards..."):
        try:
            response = requests.post(
                f"{API_URL}/flashcards/generate",
                json={
                    "document_id": doc_id,
                    "topic": topic.strip() or None,
                    "count": count,
                },
                headers=get_api_headers(),
                timeout=120,
            )
            if response.ok:
                data = response.json()
                st.session_state["current_flashcards"] = data["flashcards"]
                st.session_state["flashcard_index"] = 0
                st.session_state["show_answer"] = False
            else:
                st.error(response.json().get("detail", "Generation failed."))
        except Exception as exc:
            st.error(str(exc))

cards = st.session_state.get("current_flashcards", [])
if cards:
    index = st.session_state.get("flashcard_index", 0)
    index = max(0, min(index, len(cards) - 1))
    card = cards[index]
    st.write(f"Card {index + 1} of {len(cards)}")
    st.progress((index + 1) / len(cards))
    if st.session_state.get("show_answer"):
        st.success(card["answer"])
        if st.button("Hide Answer", use_container_width=True):
            st.session_state["show_answer"] = False
            st.rerun()
    else:
        st.info(card["question"])
        if st.button("Reveal Answer", use_container_width=True):
            st.session_state["show_answer"] = True
            st.rerun()

    left, right = st.columns(2)
    if left.button("Previous", disabled=index == 0, use_container_width=True):
        st.session_state["flashcard_index"] = index - 1
        st.session_state["show_answer"] = False
        st.rerun()
    if right.button("Next", disabled=index == len(cards) - 1, use_container_width=True):
        st.session_state["flashcard_index"] = index + 1
        st.session_state["show_answer"] = False
        st.rerun()

    try:
        export_response = requests.get(
            f"{API_URL}/flashcards/export/{doc_id}",
            headers=get_api_headers(),
            timeout=10,
        )
        if export_response.ok:
            st.download_button(
                "⬇️ Download Anki CSV",
                data=export_response.content,
                file_name=f"flashcards_{doc_id[:8]}.csv",
                mime="text/csv",
                use_container_width=True,
            )
    except Exception:
        pass
