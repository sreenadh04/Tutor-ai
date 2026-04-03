"""
MediTutor AI — Page 5: Progress Dashboard
"""

import streamlit as st
import requests
import os

st.set_page_config(page_title="Progress — MediTutor AI", page_icon="📊", layout="wide")



BASE_BACKEND = os.getenv(
    "BACKEND_URL",
    "https://meditutor-backend-v2.onrender.com"
)

API_URL = f"{BASE_BACKEND}/api/v1"

st.title("📊 Progress Dashboard")
st.caption("Track your performance, spot weak areas, and measure improvement over time.")

doc_id = st.session_state.get("selected_doc_id")
doc_name = st.session_state.get("selected_doc_name", "")
if not doc_id:
    st.warning("👈 Select a document from the sidebar to view your progress.")
    st.stop()

st.info(f"📄 Document: **{doc_name}**")

# ── Fetch Progress ────────────────────────────────────────────────────────────
try:
    resp = requests.get(
        f"{API_URL}/progress/{doc_id}",
        params={"student_id": "default_student"},
        timeout=10,
    )
    if resp.status_code == 200:
        prog = resp.json()
    elif resp.status_code == 404:
        st.error("Document not found.")
        st.stop()
    else:
        st.error(f"Failed to load progress: {resp.text}")
        st.stop()
except Exception as e:
    st.error(f"Backend error: {e}")
    st.stop()

# ── Overview Metrics ──────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("📝 Total Attempts",  prog["total_attempts"])
c2.metric("✅ Correct",         prog["total_correct"])
c3.metric("🎯 Accuracy",        f"{prog['overall_accuracy']:.1f}%")
c4.metric("⚠️ Weak Topics",     len(prog["weak_topics"]))

# ── Accuracy Bar ─────────────────────────────────────────────────────────────
acc = prog["overall_accuracy"]
bar_color = "#22c55e" if acc >= 70 else "#f59e0b" if acc >= 50 else "#ef4444"
st.markdown(f"""
<div style="margin: 1rem 0;">
  <div style="display:flex; justify-content:space-between; font-size:0.85rem; color:#64748b;">
    <span>Overall Accuracy</span><span>{acc:.1f}%</span>
  </div>
  <div style="background:#e2e8f0; border-radius:999px; height:14px; overflow:hidden; margin-top:4px;">
    <div style="width:{acc}%; height:100%; background:{bar_color}; border-radius:999px; transition:width 0.5s;"></div>
  </div>
</div>
""", unsafe_allow_html=True)

st.divider()

# ── Weak & Strong Topics ──────────────────────────────────────────────────────
col_weak, col_strong = st.columns(2)

with col_weak:
    st.subheader("⚠️ Weak Topics (< 60%)")
    if prog["weak_topics"]:
        for t in prog["weak_topics"]:
            st.markdown(
                f'<span style="display:inline-block;background:#fee2e2;color:#b91c1c;'
                f'border-radius:6px;padding:4px 10px;margin:3px;font-size:0.85rem;">🔴 {t}</span>',
                unsafe_allow_html=True,
            )
        st.caption("💡 Focus your revision on these topics!")
    else:
        st.success("No weak topics yet — keep practicing!")

with col_strong:
    st.subheader("🏆 Strong Topics (≥ 80%)")
    if prog["strong_topics"]:
        for t in prog["strong_topics"]:
            st.markdown(
                f'<span style="display:inline-block;background:#dcfce7;color:#166534;'
                f'border-radius:6px;padding:4px 10px;margin:3px;font-size:0.85rem;">🟢 {t}</span>',
                unsafe_allow_html=True,
            )
    else:
        st.info("Keep practicing to build strong topics!")

st.divider()

# ── Topic Breakdown Table ─────────────────────────────────────────────────────
st.subheader("📋 Topic-by-Topic Breakdown")

topics = prog.get("topics", [])
if topics:
    # Sort by accuracy ascending (weakest first)
    topics_sorted = sorted(topics, key=lambda x: x["accuracy"])
    
    for t in topics_sorted:
        accuracy = t["accuracy"]
        bar_c = "#22c55e" if accuracy >= 70 else "#f59e0b" if accuracy >= 50 else "#ef4444"
        icon = "🔴" if t["is_weak"] else "🟡" if accuracy < 80 else "🟢"
        
        with st.container():
            tc1, tc2, tc3 = st.columns([3, 1, 2])
            with tc1:
                st.markdown(f"{icon} **{t['topic']}**")
            with tc2:
                st.markdown(f"**{t['correct']}/{t['attempts']}**")
            with tc3:
                st.markdown(f"""
                <div style="background:#e2e8f0;border-radius:999px;height:10px;overflow:hidden;margin-top:6px;">
                  <div style="width:{accuracy}%;height:100%;background:{bar_c};border-radius:999px;"></div>
                </div>
                <div style="font-size:0.75rem;color:#64748b;text-align:right;">{accuracy:.1f}%</div>
                """, unsafe_allow_html=True)
else:
    st.info("No topic data yet. Complete some quizzes or flashcard sessions to see your progress.")

st.divider()

# ── Recent Sessions ───────────────────────────────────────────────────────────
st.subheader("🕐 Recent Study Sessions")

sessions = prog.get("recent_sessions", [])
if sessions:
    for s in sessions:
        started = s["started_at"][:16].replace("T", " ")
        acc_s = s["accuracy"]
        acc_color = "#22c55e" if acc_s >= 70 else "#f59e0b" if acc_s >= 50 else "#ef4444"
        with st.container():
            sc1, sc2, sc3, sc4 = st.columns([2, 1, 1, 1])
            sc1.markdown(f"🕐 `{started}`")
            sc2.markdown(f"**{s['total_questions']}** Qs")
            sc3.markdown(f"**{s['correct']}** ✅")
            sc4.markdown(f'<span style="color:{acc_color};font-weight:700;">{acc_s:.1f}%</span>', unsafe_allow_html=True)
        st.markdown("<hr style='margin:0.3rem 0;border-color:#f1f5f9;'>", unsafe_allow_html=True)
else:
    st.info("No study sessions yet. Take a quiz or review flashcards to track your progress.")

# ── Recommendations ───────────────────────────────────────────────────────────
if prog["weak_topics"] or prog["total_attempts"] == 0:
    st.divider()
    st.subheader("💡 Study Recommendations")
    
    if prog["total_attempts"] == 0:
        st.info("Start by taking a **📝 MCQ Quiz** or reviewing **🃏 Flashcards** to populate your progress data.")
    else:
        recs = []
        if prog["weak_topics"]:
            recs.append(f"🔴 Revise these weak topics: **{', '.join(prog['weak_topics'][:3])}**")
        if prog["overall_accuracy"] < 60:
            recs.append("📖 Re-read the relevant chapters before attempting more quizzes.")
        if prog["total_attempts"] < 20:
            recs.append("📝 Attempt more MCQs to build a solid performance baseline.")
        
        for rec in recs:
            st.markdown(f"- {rec}")
