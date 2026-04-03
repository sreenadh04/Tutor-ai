"""
MediTutor AI — Page 2: Q&A Chat with RAG
"""

import streamlit as st
import requests
import os
import time

st.set_page_config(page_title="Q&A — MediTutor AI", page_icon="💬", layout="wide")

import os

BASE_BACKEND = os.getenv(
    "BACKEND_URL",
    "https://meditutor-backend-v2.onrender.com"
)

API_URL = f"{BASE_BACKEND}/api/v1"

st.markdown("""
<style>
.chat-user { background: #eff6ff; border-radius: 12px 12px 2px 12px; padding: 0.9rem 1.2rem; margin: 0.5rem 0; }
.chat-ai   { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px 12px 12px 2px; padding: 0.9rem 1.2rem; margin: 0.5rem 0; }
.source-pill { display: inline-block; background: #ede9fe; color: #5b21b6; border-radius: 6px; padding: 0.25rem 0.6rem; font-size: 0.78rem; margin: 0.2rem; }
.source-text { background: #fafafa; border-left: 3px solid #818cf8; padding: 0.6rem 0.9rem; border-radius: 0 8px 8px 0; font-size: 0.83rem; color: #475569; margin: 0.3rem 0; }
</style>
""", unsafe_allow_html=True)

st.title("💬 Ask Questions")
st.caption("RAG-powered Q&A — every answer is grounded in your textbook with source citations.")

# Guard: need a document selected
doc_id = st.session_state.get("selected_doc_id")
doc_name = st.session_state.get("selected_doc_name", "Unknown")
if not doc_id:
    st.warning("👈 Please upload and select a document from the sidebar first.")
    st.stop()

st.info(f"📄 Active document: **{doc_name}**")

# ── Session Management ────────────────────────────────────────────────────────
if not st.session_state.get("session_id"):
    try:
        r = requests.post(
            f"{API_URL}/progress/session/start",
            json={"document_id": doc_id, "student_id": "default_student"},
            timeout=5,
        )
        if r.ok:
            st.session_state["session_id"] = r.json()["session_id"]
    except Exception:
        pass

# ── Chat History Display ──────────────────────────────────────────────────────
chat_container = st.container()

if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

with chat_container:
    for msg in st.session_state["chat_history"]:
        if msg["role"] == "user":
            st.markdown(f'<div class="chat-user">🧑‍🎓 <b>You:</b> {msg["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-ai">🧠 <b>MediTutor AI:</b><br>{msg["content"]}</div>', unsafe_allow_html=True)
            
            # Show sources if available
            if msg.get("sources"):
                with st.expander(f"📚 {len(msg['sources'])} Source(s) used", expanded=False):
                    for i, src in enumerate(msg["sources"], 1):
                        page_label = f"Page {src['page_number']}" if src.get("page_number") else "Unknown page"
                        score = src.get("relevance_score", 0)
                        st.markdown(
                            f'<span class="source-pill">Source {i} • {page_label} • score: {score:.2f}</span>',
                            unsafe_allow_html=True,
                        )
                        st.markdown(
                            f'<div class="source-text">{src["text"]}</div>',
                            unsafe_allow_html=True,
                        )
            
            if msg.get("model_used"):
                st.caption(f"🤖 Model: `{msg['model_used']}`")

# ── Input Area ────────────────────────────────────────────────────────────────
st.divider()

col1, col2 = st.columns([5, 1])
with col1:
    question = st.text_input(
        "Ask a question about your textbook...",
        placeholder="e.g. What is the mechanism of action of beta blockers?",
        key="qa_input",
        label_visibility="collapsed",
    )
with col2:
    ask_btn = st.button("Ask 🔍", type="primary", use_container_width=True)

# ── Example Questions ─────────────────────────────────────────────────────────
with st.expander("💡 Example questions"):
    examples = [
        "What is the main topic of Chapter 1?",
        "Explain the key concepts in this material.",
        "What are the most important definitions?",
        "Summarize the treatment options discussed.",
        "What are the contraindications mentioned?",
    ]
    cols = st.columns(2)
    for i, ex in enumerate(examples):
        if cols[i % 2].button(ex, key=f"ex_{i}", use_container_width=True):
            question = ex
            ask_btn = True

# ── Process Question ──────────────────────────────────────────────────────────
if ask_btn and question and question.strip():
    st.session_state["chat_history"].append({"role": "user", "content": question})

    with st.spinner("🔍 Searching textbook and generating answer..."):
        try:
            payload = {
                "document_id": doc_id,
                "question": question,
                "session_id": st.session_state.get("session_id"),
            }
            resp = requests.post(f"{API_URL}/qa/ask", json=payload, timeout=90)

            if resp.status_code == 200:
                data = resp.json()
                answer = data["answer"]
                sources = data.get("sources", [])
                model_used = data.get("model_used", "unknown")
                cached = data.get("cached", False)

                st.session_state["chat_history"].append({
                    "role": "assistant",
                    "content": answer,
                    "sources": sources,
                    "model_used": model_used + (" ⚡cached" if cached else ""),
                })
                st.rerun()

            elif resp.status_code == 404:
                st.error("❌ Document index not found. Please re-upload the PDF.")
            elif resp.status_code == 503:
                st.error("❌ AI models unavailable. Check API keys in your .env file.")
            else:
                st.error(f"❌ Error: {resp.json().get('detail', 'Unknown error')}")

        except requests.exceptions.Timeout:
            st.error("⏱️ Request timed out. The free AI model may be slow — please try again.")
        except requests.exceptions.ConnectionError:
            st.error("❌ Cannot connect to backend. Is the FastAPI server running?")
        except Exception as e:
            st.error(f"❌ Unexpected error: {e}")

# ── Clear Chat ────────────────────────────────────────────────────────────────
if st.session_state["chat_history"]:
    if st.button("🗑️ Clear Chat History"):
        st.session_state["chat_history"] = []
        st.rerun()
