"""
Shared frontend helpers for user-scoped API access.
"""

import os
import uuid

import requests
import streamlit as st


def get_backend_base() -> str:
    return os.getenv("BACKEND_URL", "https://meditutor-backend-v2.onrender.com")


def get_api_url() -> str:
    return f"{get_backend_base()}/api/v1"


def get_or_create_user_id() -> str:
    user_id = st.session_state.get("user_id")
    if not user_id:
        user_id = str(uuid.uuid4())
        st.session_state["user_id"] = user_id
    return user_id


def get_api_headers(include_content_type: bool = True) -> dict:
    headers = {
        "X-User-ID": get_or_create_user_id(),
        "Accept": "application/json",
    }
    if include_content_type:
        headers["Content-Type"] = "application/json"
    return headers


def get_upload_headers() -> dict:
    return get_api_headers(include_content_type=False)


def ensure_study_session(document_id: str, api_url: str | None = None) -> str | None:
    if not document_id:
        return None

    if (
        st.session_state.get("session_id")
        and st.session_state.get("session_doc_id") == document_id
    ):
        return st.session_state["session_id"]

    api_base = api_url or get_api_url()
    response = requests.post(
        f"{api_base}/progress/session/start",
        json={"document_id": document_id},
        headers=get_api_headers(),
        timeout=5,
    )
    if response.ok:
        session_id = response.json()["session_id"]
        st.session_state["session_id"] = session_id
        st.session_state["session_doc_id"] = document_id
        return session_id
    return None
