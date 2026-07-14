"""Chatbot session/navigation tests.

Uses the fake LLM mode and an in-memory store, so no OpenAI key or database is
needed. Questions are set inline via `set_questions`.
"""

from typing import Any

from backend.models import Question
from backend.services.ai_service import SurveyAIService
from backend.services.chatbot import SurveyChatbotService
from backend.services.llm_service import OpenAILLMService


class MemoryStore:
    """In-memory SessionStore/SurveyStore implementation for tests."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    def save(self, key: str, payload: dict[str, Any]) -> None:
        self._data[key] = payload

    def load(self, key: str) -> dict[str, Any] | None:
        return self._data.get(key)

    def delete(self, key: str) -> bool:
        return self._data.pop(key, None) is not None

    def list_by_survey(self, survey_id: str) -> list[dict[str, Any]]:
        return [s for s in self._data.values() if s.get("survey_id") == survey_id]


def make_service() -> SurveyChatbotService:
    ai_service = SurveyAIService(llm_service=OpenAILLMService(fake_mode=True))
    service = SurveyChatbotService(store=MemoryStore(), survey_store=MemoryStore(), ai_service=ai_service)
    service.set_questions([
        Question(id="q01", category="Time", question_type="distribution",
                 prompt="How is your time divided?", options=["work", "meetings"]),
        Question(id="q02", category="Satisfaction", question_type="rating",
                 prompt="Rate your overall satisfaction.", min_value=1, max_value=5),
    ])
    return service


def test_answer_navigate_back_and_edit():
    service = make_service()
    session = service.create_session()

    # Answer Q1 (distribution) and advance to Q2.
    session = service.submit_message(session.session_id, "30% work, 70% meetings")
    assert session.current_question is not None
    assert session.current_question.number == 2

    # Go back to Q1.
    session = service.submit_message(session.session_id, "go back to question 1")
    assert session.current_question is not None
    assert session.current_question.number == 1
    assert "Previous answer" in session.assistant_message

    # Submit the updated Q1 answer and return to Q2.
    session = service.submit_message(session.session_id, "50% work, 50% meetings")
    assert session.current_question is not None
    assert session.current_question.number == 2
    assert session.responses["q01"]["raw_answer"] == "50% work, 50% meetings"


def test_invalid_navigation_number_is_handled():
    service = make_service()
    session = service.create_session()

    session = service.submit_message(session.session_id, "go back to question 99")

    assert session.current_question is not None
    assert session.current_question.number == 1
    assert "between 1 and 2" in session.assistant_message


def test_show_progress_intent():
    service = make_service()
    session = service.create_session()

    session = service.submit_message(session.session_id, "show progress")

    assert "0/2" in session.assistant_message


def test_multiple_selection_enforces_max_choices():
    ai_service = SurveyAIService(llm_service=OpenAILLMService(fake_mode=True))
    service = SurveyChatbotService(store=MemoryStore(), survey_store=MemoryStore(), ai_service=ai_service)
    service.set_questions([
        Question(id="m1", category="Work", question_type="multiple_selection",
                 prompt="Pick your modes", options=["A. onsite", "B. hybrid", "C. remote"], max_choices=2),
        Question(id="m2", category="X", question_type="free_text", prompt="Why?", min_length=2),
    ])
    session = service.create_session()

    # 3 selections with a cap of 2 must be rejected — stay on Q1, nothing saved.
    session = service.submit_message(session.session_id, "onsite, hybrid, remote")
    assert session.current_question is not None
    assert session.current_question.number == 1
    assert "m1" not in session.responses
    assert "up to 2" in session.assistant_message

    # 2 selections are accepted and advance to Q2.
    session = service.submit_message(session.session_id, "onsite, hybrid")
    assert session.current_question is not None
    assert session.current_question.number == 2
    assert session.responses["m1"]["response"]["values"] == ["A. onsite", "B. hybrid"]
