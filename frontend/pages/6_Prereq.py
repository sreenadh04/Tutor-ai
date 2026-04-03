"""
MediTutor AI — Page 6: Prerequisite Checker
"""

import streamlit as st
import requests
import os

st.set_page_config(page_title="Prerequisites — MediTutor AI", page_icon="🔍", layout="wide")

API_URL = os.getenv("MEDITUTOR_API_URL", "http://localhost:8000/api/v1")

st.title("🔍 Prerequisite Checker")
st.caption("Before diving into a complex topic, find out what foundational knowledge you need first.")

doc_id = st.session_state.get("selected_doc_id")
doc_name = st.session_state.get("selected_doc_name", "")
if not doc_id:
    st.warning("👈 Please select a document first.")
    st.stop()

st.info(f"📄 Document: **{doc_name}**")

# ── Input ─────────────────────────────────────────────────────────────────────
with st.form("prereq_form"):
    query = st.text_area(
        "What topic are you about to study?",
        placeholder="e.g. Mechanism of action of ACE inhibitors\ne.g. How does the renin-angiotensin system work?",
        height=100,
    )
    submitted = st.form_submit_button("🔍 Check Prerequisites", type="primary", use_container_width=True)

# ── Example queries ───────────────────────────────────────────────────────────
st.markdown("**💡 Try these examples:**")
examples = [
    "Cardiac glycosides mechanism",
    "Blood-brain barrier permeability",
    "Immune response to infection",
    "Pharmacokinetics of drugs",
]
cols = st.columns(4)
for i, ex in enumerate(examples):
    if cols[i].button(ex, key=f"ex_{i}", use_container_width=True):
        query = ex
        submitted = True

# ── Process ───────────────────────────────────────────────────────────────────
if submitted and query and query.strip():
    with st.spinner("🔍 Analyzing prerequisites..."):
        try:
            payload = {
                "document_id": doc_id,
                "query": query.strip(),
                "student_id": "default_student",
            }
            resp = requests.post(f"{API_URL}/prereq/check", json=payload, timeout=60)

            if resp.status_code == 200:
                data = resp.json()
                st.success(f"Analysis complete — `{data.get('model_used', 'AI')}`")

                # ── Weak related topics (from actual progress data) ──────────
                weak_related = data.get("weak_related_topics", [])
                if weak_related:
                    st.markdown("""
                    <div style="background:#fff1f2;border:1px solid #fecdd3;border-radius:12px;padding:1rem 1.2rem;margin-bottom:1rem;">
                    <h4 style="color:#b91c1c;margin:0 0 0.5rem;">⚠️ Based on your quiz history — you're weak on:</h4>
                    """, unsafe_allow_html=True)
                    for wt in weak_related:
                        st.markdown(f"- 🔴 **{wt}**")
                    st.markdown("</div>", unsafe_allow_html=True)

                col1, col2 = st.columns(2)

                with col1:
                    st.subheader("🧩 Missing Concepts")
                    missing = data.get("missing_concepts", [])
                    if missing:
                        for m in missing:
                            st.markdown(f"- ❓ {m}")
                    else:
                        st.success("No obvious missing concepts detected!")

                    st.subheader("📚 Prerequisite Topics")
                    prereqs = data.get("prerequisite_topics", [])
                    if prereqs:
                        for i, p in enumerate(prereqs, 1):
                            st.markdown(f"{i}. 📖 {p}")
                    else:
                        st.info("No specific prerequisites identified.")

                with col2:
                    st.subheader("🗺️ Recommended Study Path")
                    recs = data.get("study_recommendations", [])
                    if recs:
                        for i, r in enumerate(recs, 1):
                            st.markdown(
                                f'<div style="background:#f0fdf4;border-left:3px solid #22c55e;'
                                f'padding:0.6rem 0.9rem;border-radius:0 8px 8px 0;margin:0.4rem 0;">'
                                f'<b>Step {i}:</b> {r}</div>',
                                unsafe_allow_html=True,
                            )
                    else:
                        st.info("No specific recommendations generated.")

                # ── Action buttons ────────────────────────────────────────────
                st.divider()
                c1, c2, c3 = st.columns(3)
                with c1:
                    if prereqs and st.button("💬 Ask about prerequisites", use_container_width=True):
                        first_prereq = prereqs[0]
                        st.session_state["chat_history"] = st.session_state.get("chat_history", [])
                        st.session_state["chat_history"].append({
                            "role": "user",
                            "content": f"Explain {first_prereq} in simple terms.",
                        })
                        st.switch_page("pages/2_QA_Chat.py")
                with c2:
                    if prereqs and st.button("🃏 Make flashcards on prereqs", use_container_width=True):
                        st.session_state["prereq_topic"] = prereqs[0] if prereqs else None
                        st.switch_page("pages/3_Flashcards.py")
                with c3:
                    if prereqs and st.button("📝 Quiz on prerequisites", use_container_width=True):
                        st.session_state["prereq_topic"] = prereqs[0] if prereqs else None
                        st.switch_page("pages/4_MCQ_Quiz.py")

            elif resp.status_code == 404:
                st.error("❌ Document not found. Re-upload the PDF.")
            else:
                st.error(f"❌ Error: {resp.json().get('detail', 'Unknown')}")

        except requests.exceptions.Timeout:
            st.error("⏱️ Request timed out. Try again.")
        except Exception as e:
            st.error(f"❌ Error: {e}")

# ── How it works ──────────────────────────────────────────────────────────────
with st.expander("ℹ️ How does this work?"):
    st.markdown("""
    The Prerequisite Checker combines two sources:

    1. **Your progress data** — Topics you've attempted and scored low on (< 60%) are flagged as weak.
    2. **AI analysis** — The LLM analyzes your query and the relevant textbook content to identify what conceptual foundations you need.

    Together, these give you a personalised study roadmap: what to study first, in what order, and where your current gaps are.
    """)
