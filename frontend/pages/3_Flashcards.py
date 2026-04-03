"""
MediTutor AI — Page 3: Flashcards
"""

import streamlit as st
import requests
import os

st.set_page_config(page_title="Flashcards — MediTutor AI", page_icon="🃏", layout="wide")

BASE_BACKEND = os.getenv(
    "BACKEND_URL",
    "https://meditutor-backend-v2.onrender.com"
)

API_URL = f"{BASE_BACKEND}/api/v1"

st.markdown("""
<style>
.fc-question {
    background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
    color: white; border-radius: 16px; padding: 2.5rem 2rem;
    text-align: center; min-height: 160px; font-size: 1.15rem;
    box-shadow: 0 8px 24px rgba(79,70,229,0.3);
}
.fc-answer {
    background: linear-gradient(135deg, #059669 0%, #10b981 100%);
    color: white; border-radius: 16px; padding: 2.5rem 2rem;
    text-align: center; min-height: 160px; font-size: 1.1rem;
    box-shadow: 0 8px 24px rgba(5,150,105,0.3);
}
.diff-easy   { background:#dcfce7; color:#166534; border-radius:6px; padding:2px 8px; font-size:0.8rem; }
.diff-medium { background:#fef9c3; color:#854d0e; border-radius:6px; padding:2px 8px; font-size:0.8rem; }
.diff-hard   { background:#fee2e2; color:#991b1b; border-radius:6px; padding:2px 8px; font-size:0.8rem; }
</style>
""", unsafe_allow_html=True)

st.title("🃏 Flashcards")
st.caption("Auto-generated study cards — flip to reveal the answer. Export to Anki.")

doc_id = st.session_state.get("selected_doc_id")
doc_name = st.session_state.get("selected_doc_name", "")
if not doc_id:
    st.warning("👈 Please select a document first.")
    st.stop()

st.info(f"📄 Document: **{doc_name}**")

# ── Generation Controls ───────────────────────────────────────────────────────
with st.expander("⚙️ Generation Settings", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        topic = st.text_input(
            "Topic / Chapter (optional)",
            placeholder="e.g. Cardiac Pharmacology, Chapter 3",
            help="Leave blank to generate from the whole document."
        )
    with col2:
        count = st.slider("Number of flashcards", 5, 30, 10)

    gen_btn = st.button("✨ Generate Flashcards", type="primary", use_container_width=True)

if gen_btn:
    with st.spinner("🤖 Generating flashcards... (may take 15-30s on free tier)"):
        try:
            payload = {
                "document_id": doc_id,
                "count": count,
                "topic": topic.strip() if topic.strip() else None,
            }
            resp = requests.post(f"{API_URL}/flashcards/generate", json=payload, timeout=120)

            if resp.status_code == 200:
                data = resp.json()
                st.session_state["current_flashcards"] = data["flashcards"]
                st.session_state["flashcard_index"] = 0
                st.session_state["show_answer"] = False
                model = data.get("model_used", "")
                cached = data.get("cached", False)
                st.success(f"✅ Generated {data['total_generated']} flashcards — Model: `{model}`{'  ⚡ (cached)' if cached else ''}")
            else:
                st.error(f"❌ {resp.json().get('detail', 'Generation failed')}")
        except requests.exceptions.Timeout:
            st.error("⏱️ Timed out. Try reducing the count or try again.")
        except Exception as e:
            st.error(f"❌ {e}")

# ── Flashcard Viewer ──────────────────────────────────────────────────────────
cards = st.session_state.get("current_flashcards", [])

if cards:
    st.divider()
    idx = st.session_state.get("flashcard_index", 0)
    idx = max(0, min(idx, len(cards) - 1))
    card = cards[idx]

    # Progress bar
    progress_pct = (idx + 1) / len(cards)

    difficulty = card.get("difficulty", "medium")
    topic = card.get("topic", "General")

    st.markdown(
        f"**Card {idx+1} of {len(cards)}** — "
        f'<span class="diff-{difficulty}">{difficulty}</span>'
        + " &nbsp; 🏷️ " + topic,
        unsafe_allow_html=True,
    )
    st.progress(progress_pct)
    st.markdown("<br>", unsafe_allow_html=True)

    # Card display
    show = st.session_state.get("show_answer", False)

    if not show:
        st.markdown(
            f'<div class="fc-question">❓<br><br><b>{card["question"]}</b></div>',
            unsafe_allow_html=True,
        )
        if st.button("👁️ Reveal Answer", use_container_width=True):
            st.session_state["show_answer"] = True
            st.rerun()
    else:
        st.markdown(
            f'<div class="fc-answer">✅<br><br>{card["answer"]}</div>',
            unsafe_allow_html=True,
        )
        if st.button("🔁 Hide Answer", use_container_width=True):
            st.session_state["show_answer"] = False
            st.rerun()

    # Navigation
    st.markdown("<br>", unsafe_allow_html=True)
    nav1, nav2, nav3 = st.columns([1, 2, 1])
    with nav1:
        if st.button("⬅️ Previous", disabled=(idx == 0), use_container_width=True):
            st.session_state["flashcard_index"] = idx - 1
            st.session_state["show_answer"] = False
            st.rerun()
    with nav2:
        jump = st.number_input("Jump to card #", 1, len(cards), idx + 1, label_visibility="collapsed")
        if st.button("Jump", use_container_width=True):
            st.session_state["flashcard_index"] = int(jump) - 1
            st.session_state["show_answer"] = False
            st.rerun()
    with nav3:
        if st.button("Next ➡️", disabled=(idx == len(cards) - 1), use_container_width=True):
            st.session_state["flashcard_index"] = idx + 1
            st.session_state["show_answer"] = False
            st.rerun()

    # ── All Cards Table ───────────────────────────────────────────────────────
    st.divider()
    with st.expander("📋 View All Flashcards"):
        for i, c in enumerate(cards):
            with st.container():
                q_col, a_col = st.columns([1, 1])
                with q_col:
                    st.markdown(f"**Q{i+1}:** {c['question']}")
                with a_col:
                    st.markdown(f"**A:** {c['answer']}")
                st.caption(f"Topic: {c.get('topic','—')} | Difficulty: {c.get('difficulty','medium')}")
                st.divider()

    # ── Export Button ─────────────────────────────────────────────────────────
    st.subheader("📥 Export to Anki")
    try:
        csv_resp = requests.get(f"{API_URL}/flashcards/export/{doc_id}", timeout=10)
        if csv_resp.ok:
            st.download_button(
                "⬇️ Download Anki CSV",
                data=csv_resp.content,
                file_name=f"flashcards_{doc_id[:8]}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            st.info("Generate flashcards first, then export.")
    except Exception as e:
        st.warning(f"Export unavailable: {e}")
