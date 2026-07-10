from __future__ import annotations

import json
import os
from typing import Any

import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="Employee Survey",
    page_icon="💬",
    layout="centered",
)


class ApiError(RuntimeError):
    pass


def api_request(method: str, path: str, json_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{BACKEND_URL}{path}"
    print(f"[API] {method} {url}", flush=True)
    try:
        response = requests.request(method=method, url=url, json=json_payload, timeout=60)
    except requests.RequestException as exc:
        print(f"[API] ERROR connection failed: {exc}", flush=True)
        raise ApiError("Could not connect. Please try again later.") from exc

    print(f"[API] {response.status_code} <- {method} {url}", flush=True)
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        print(f"[API] ERROR {response.status_code}: {detail}", flush=True)
        raise ApiError(f"Error {response.status_code}: {detail}")

    return response.json()


def get_survey_id() -> str | None:
    return st.query_params.get("survey_id")


def start_session(employee_id: str | None = None) -> None:
    survey_id = get_survey_id()
    payload: dict[str, Any] = {"employee_id": employee_id or None}
    if survey_id:
        payload["survey_id"] = survey_id
    session = api_request("POST", "/sessions", payload)
    st.session_state.session = session
    clear_pending_message()


def send_message(message: str) -> None:
    session_id = st.session_state.session["session_id"]
    updated_session = api_request("POST", f"/sessions/{session_id}/message", {"message": message})
    st.session_state.session = updated_session


def clear_pending_message() -> None:
    st.session_state.pop("pending_user_message", None)
    st.session_state["is_waiting_for_response"] = False


def queue_user_message(message: str) -> None:
    st.session_state.pending_user_message = message
    st.session_state.is_waiting_for_response = True


def reset_session() -> None:
    session = st.session_state.get("session")
    if session:
        try:
            api_request("DELETE", f"/sessions/{session['session_id']}")
        except ApiError:
            pass
    st.session_state.pop("session", None)
    clear_pending_message()


def get_multi_select_key(question_id: str) -> str:
    """Returns the session_state key used to store multi-select toggle state."""
    return f"multi_select_{question_id}"


def reset_multi_select(question_id: str) -> None:
    """Clears any stored toggle selections for the given question."""
    key = get_multi_select_key(question_id)
    st.session_state.pop(key, None)


def render_answer_buttons(session: dict[str, Any], is_waiting: bool) -> None:
    """
    Renders clickable answer buttons for single_selection, multiple_selection,
    and rating question types. For all other types, renders nothing (chat only).
    """
    
    if session.get("completed"):
        return

    current_question = session.get("current_question")
    if not current_question:
        return

    question_type = current_question.get("question_type", "")
    question_id = current_question.get("id", "unknown")
    options = current_question.get("options") or []

    #  Single selection
    if question_type == "single_selection" and options:
        st.write("**Choose one:**")
        cols = st.columns(min(len(options), 3))
        for idx, option in enumerate(options):
            col = cols[idx % len(cols)]
            with col:
                if st.button(
                    option,
                    key=f"single_{question_id}_{idx}_{option}",
                    disabled=is_waiting,
                    use_container_width=True,
                ):
                    queue_user_message(option)
                    st.rerun()

    #  Rating 
    elif question_type == "rating":
        min_val = current_question.get("min_value")
        max_val = current_question.get("max_value")
        if min_val is not None and max_val is not None:
            rating_range = list(range(int(min_val), int(max_val) + 1))
            st.write(f"**Rate from {min_val} to {max_val}:**")
            cols = st.columns(len(rating_range))
            for idx, value in enumerate(rating_range):
                with cols[idx]:
                    if st.button(
                        str(value),
                        key=f"rating_{question_id}_{value}",
                        disabled=is_waiting,
                        use_container_width=True,
                    ):
                        queue_user_message(str(value))
                        st.rerun()

    #  Multiple selection
    elif question_type == "multiple_selection" and options:
        max_choices = current_question.get("max_choices")
        state_key = get_multi_select_key(question_id)

        
        if state_key not in st.session_state:
            st.session_state[state_key] = set()

        selected: set = st.session_state[state_key]

        if max_choices:
            st.write(f"**Choose up to {max_choices} options** (click to select/deselect):")
        else:
            st.write("**Choose all that apply** (click to select/deselect):")

        
        cols = st.columns(min(len(options), 3))
        for idx, option in enumerate(options):
            col = cols[idx % len(cols)]
            with col:
                is_selected = option in selected
                btn_type = "primary" if is_selected else "secondary"
                label = f"✓ {option}" if is_selected else option

                if st.button(
                    label,
                    key=f"multi_{question_id}_{idx}_{option}",
                    disabled=is_waiting,
                    type=btn_type,
                    use_container_width=True,
                ):
                    if is_selected:
                        # Deselect
                        selected.discard(option)
                    else:
                        # Select 
                        if max_choices and len(selected) >= int(max_choices):
                            st.warning(f"You can only select up to {max_choices} options.")
                        else:
                            selected.add(option)
                    
                    st.session_state[state_key] = selected
                    st.rerun()

        # Next button 
        st.write("")  
        nothing_selected = len(selected) == 0
        if st.button(
            "Next →",
            key=f"multi_next_{question_id}",
            disabled=is_waiting or nothing_selected,
            type="primary",
            use_container_width=False,
        ):
            answer = ", ".join(selected)
            reset_multi_select(question_id)
            queue_user_message(answer)
            st.rerun()

        if nothing_selected and not is_waiting:
            st.caption("Select at least one option, then click Next.")


def render_sidebar(session: dict[str, Any]) -> None:
    with st.sidebar:
        st.title("Survey Progress")
        progress = session["progress"]
        total = session["total_questions"]
        st.progress(progress / total if total else 0)
        st.caption(f"{progress}/{total} questions answered")
        st.caption("Tip: type `go back to question 1` to edit a previous answer. You can also ask `show progress` or `help`.")

        current_question = session.get("current_question")
        if current_question:
            st.divider()
            st.subheader("Current Question")
            st.write(f"**Category:** {current_question['category']}")
            st.write(f"**Type:** {current_question['question_type']}")
            st.write(f"**Expected format:** `{current_question['expected_format']}`")

            options = current_question.get("options") or []
            if options:
                st.write("**Options:**")
                for option in options:
                    st.write(f"- {option}")

        st.divider()
        if st.button("Reset survey", use_container_width=True):
            reset_session()
            st.rerun()


def render_chat(session: dict[str, Any]) -> None:
    for message in session["chat_history"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def render_pending_exchange_and_process() -> None:
    """Shows the user's answer plus an animated loader, runs the blocking
    backend call inside the loader, then reruns to display the next question."""
    pending_message = st.session_state.get("pending_user_message")
    if not pending_message:
        return

    with st.chat_message("user"):
        st.markdown(pending_message)

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                send_message(pending_message)
            except ApiError as exc:
                clear_pending_message()
                st.error(str(exc))
                return

    clear_pending_message()
    st.rerun()


def render_completion(session: dict[str, Any]) -> None:
    if not session["completed"]:
        return

    st.success("Survey completed successfully.")
    responses_json = json.dumps(session["responses"], indent=2, ensure_ascii=False)

    with st.expander("View saved responses", expanded=True):
        st.json(session["responses"])

    st.download_button(
        label="Download responses JSON",
        data=responses_json,
        file_name=f"survey_responses_{session['session_id']}.json",
        mime="application/json",
        use_container_width=True,
    )


def render_landing() -> None:
    survey_id = get_survey_id()

    st.title("Employee Survey")

    if survey_id:
        try:
            survey = api_request("GET", f"/surveys/{survey_id}")
            title = survey.get("title") or "Employee Survey"
            total = survey["total_questions"]
            st.info(f"**{title}** — {total} questions")
        except ApiError:
            st.warning("Survey not found. Please check your link.")
            return

    st.write("Welcome. Click the button below to begin the survey.")

    employee_id = st.text_input("Your name or ID (optional)", placeholder="Optional")

    if st.button("Start survey", type="primary", use_container_width=True):
        try:
            start_session(employee_id=employee_id)
            st.rerun()
        except ApiError as exc:
            st.error(str(exc))


def main() -> None:
    if "is_waiting_for_response" not in st.session_state:
        st.session_state.is_waiting_for_response = False

    if "session" not in st.session_state:
        render_landing()
        return

    session = st.session_state.session
    is_waiting = bool(st.session_state.get("is_waiting_for_response"))

    render_sidebar(session)

    # While waiting, don't redraw the old conversation (the question just
    # answered) or the stale buttons/input. Show only the user's answer and an
    # animated loader, then process and rerun to reveal the next question.
    if is_waiting:
        render_pending_exchange_and_process()
        return

    render_chat(session)
    render_answer_buttons(session, is_waiting)

    render_completion(session)

    placeholder = "Type: go back to question 1" if session["completed"] else "Type your answer here..."
    user_message = st.chat_input(placeholder)
    if user_message:
        queue_user_message(user_message)
        st.rerun()


if __name__ == "__main__":
    main()