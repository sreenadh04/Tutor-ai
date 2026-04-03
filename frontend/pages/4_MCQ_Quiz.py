"""
MediTutor AI - Page 4: MCQ Quiz
"""

import sys
from pathlib import Path

import requests
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from common import ensure_study_session, get_api_headers, get_api_url

st.set_page_config(page_title="MCQ Quiz - MediTutor AI", page_icon="📝", layout="wide")

API_URL = get_api_url()
doc_id = st.session_state.get("selected_doc_id")
doc_name = st.session_state.get("selected_doc_name", "")

st.title("📝 MCQ Quiz")
st.caption("Generate and grade quizzes from your selected document.")

if not doc_id:
    st.warning("Please select a document first.")
    st.stop()

st.info(f"📄 Document: **{doc_name}**")
try:
    ensure_study_session(doc_id, API_URL)
except Exception:
    pass

topic_default = st.session_state.pop("prereq_topic", "")
topic = st.text_input("Topic (optional)", value=topic_default)
count = st.slider("Number of questions", 3, 20, 5)

if st.button("🎯 Generate Quiz", type="primary", use_container_width=True):
    with st.spinner("Generating quiz..."):
        response = requests.post(
            f"{API_URL}/mcq/generate",
            json={"document_id": doc_id, "topic": topic.strip() or None, "count": count},
            headers=get_api_headers(),
            timeout=120,
        )
        if response.ok:
            data = response.json()
            st.session_state["current_mcqs"] = data["questions"]
            st.session_state["mcq_answers"] = {}
            st.session_state["quiz_submitted"] = False
            st.session_state["quiz_results"] = None
            st.rerun()
        else:
            st.error(response.json().get("detail", "Generation failed."))

questions = st.session_state.get("current_mcqs", [])
if questions and not st.session_state.get("quiz_submitted", False):
    for index, question in enumerate(questions, start=1):
        st.subheader(f"Q{index}. {question['question']}")
        labels = [f"{chr(65 + option_index)}. {option}" for option_index, option in enumerate(question["options"])]
        selected = st.radio(
            f"Answer for question {index}",
            options=range(len(labels)),
            format_func=lambda value: labels[value],
            key=f"mcq_{question['id']}",
            index=st.session_state["mcq_answers"].get(question["id"]),
        )
        st.session_state["mcq_answers"][question["id"]] = selected

    if st.button("📤 Submit Quiz", type="primary", use_container_width=True):
        answers_payload = [
            {
                "question_id": question_id,
                "selected_index": selected_index,
                "topic": next((question["topic"] for question in questions if question["id"] == question_id), "General"),
            }
            for question_id, selected_index in st.session_state["mcq_answers"].items()
        ]
        response = requests.post(
            f"{API_URL}/mcq/submit",
            json={
                "document_id": doc_id,
                "session_id": st.session_state.get("session_id"),
                "answers": answers_payload,
            },
            headers=get_api_headers(),
            timeout=30,
        )
        if response.ok:
            st.session_state["quiz_results"] = response.json()
            st.session_state["quiz_submitted"] = True
            st.rerun()
        else:
            st.error(response.json().get("detail", "Submission failed."))

if st.session_state.get("quiz_submitted") and st.session_state.get("quiz_results"):
    result = st.session_state["quiz_results"]
    st.metric("Score", f"{result['score']:.1f}%")
    st.metric("Correct", f"{result['correct']} / {result['total']}")
    for feedback in result.get("feedback", []):
        icon = "✅" if feedback["is_correct"] else "❌"
        with st.expander(f"{icon} {feedback['question'][:80]}"):
            st.write(feedback["explanation"])
    if st.button("🔄 Start New Quiz", use_container_width=True):
        st.session_state["current_mcqs"] = []
        st.session_state["quiz_submitted"] = False
        st.session_state["quiz_results"] = None
        st.session_state["mcq_answers"] = {}
        st.rerun()
