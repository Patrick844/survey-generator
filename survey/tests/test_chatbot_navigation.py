from pathlib import Path

from backend.services.ai_service import SurveyAIService
from backend.services.chatbot import SurveyChatbotService
from backend.services.llm_service import OpenAILLMService
from backend.services.storage import JsonSessionStore


def make_service(tmp_path: Path) -> SurveyChatbotService:
    ai_service = SurveyAIService(llm_service=OpenAILLMService(fake_mode=True))
    return SurveyChatbotService(store=JsonSessionStore(base_dir=tmp_path), ai_service=ai_service)


def test_go_back_to_question_updates_answer_and_returns_to_current_question(tmp_path):
    service = make_service(tmp_path)
    session = service.create_session()

    # Answer Q1 and move to Q2.
    session = service.submit_message(
        session.session_id,
        "A 20%, B 20%, C 20%, D 20%, E 10%, F 5%, G 3%, H 2%",
    )
    assert session.current_question is not None
    assert session.current_question.number == 2

    # Ask to edit Q1. In production this is detected by OpenAI.
    session = service.submit_message(session.session_id, "go back to question 1")
    assert session.current_question is not None
    assert session.current_question.number == 1
    assert "Previous answer" in session.assistant_message

    # Submit updated Q1 answer.
    session = service.submit_message(
        session.session_id,
        "A 10%, B 20%, C 20%, D 20%, E 10%, F 10%, G 5%, H 5%",
    )
    assert session.current_question is not None
    assert session.current_question.number == 2
    assert session.responses["q01"]["raw_answer"] == "A 10%, B 20%, C 20%, D 20%, E 10%, F 10%, G 5%, H 5%"
    assert session.responses["q01"]["response"] == {
        "A": 10,
        "B": 20,
        "C": 20,
        "D": 20,
        "E": 10,
        "F": 10,
        "G": 5,
        "H": 5,
    }


def test_invalid_navigation_question_number_is_handled(tmp_path):
    service = make_service(tmp_path)
    session = service.create_session()

    session = service.submit_message(session.session_id, "go back to question 99")

    assert session.current_question is not None
    assert session.current_question.number == 1
    assert "between 1 and 30" in session.assistant_message


def test_show_progress_intent(tmp_path):
    service = make_service(tmp_path)
    session = service.create_session()

    session = service.submit_message(session.session_id, "show progress")

    assert "0/30" in session.assistant_message
