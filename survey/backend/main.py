from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.models import (
    ChatRequest,
    CreateSessionRequest,
    CreateSurveyRequest,
    DeleteResponse,
    GlobalQuestionsResponse,
    HealthResponse,
    Question,
    QuestionCountResponse,
    QuestionListResponse,
    QuestionUpdateResponse,
    SessionResponse,
    SetQuestionsRequest,
    StatusResponse,
    SurveyResponse,
    SurveyResponsesResponse,
)
from backend.services.chatbot import SurveyChatbotService
from backend.services.storage import init_db

app = FastAPI(
    title="Employee Survey Chatbot API",
    version="0.3.0",
    description=(
        "OpenAI-powered backend for a smart employee survey chatbot.\n\n"
        "**Typical flow:**\n"
        "1. Admin uses the React generator to call `POST /surveys` → receives a `survey_url`.\n"
        "2. Employees open the `survey_url` (Streamlit), which calls `POST /sessions` with the `survey_id`.\n"
        "3. Each employee message goes to `POST /sessions/{session_id}/message`.\n"
        "4. When complete, admin calls `GET /surveys/{survey_id}/responses` to view all answers."
    ),
    contact={"name": "300-30-3 Team"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()
chatbot_service = SurveyChatbotService()


# ── Health ────────────────────────────────────────────────────────────────────

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Health check",
    description="Returns `{status: ok}` when the service is up.",
)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


# ── Global question list (legacy / default set) ───────────────────────────────

@app.get(
    "/questions",
    response_model=GlobalQuestionsResponse,
    tags=["Questions (global)"],
    summary="Get default question set",
    description="Returns the in-memory default question set (empty by default; use `PUT /questions` to set or `POST /surveys` for persistent surveys).",
)
def get_questions() -> GlobalQuestionsResponse:
    return GlobalQuestionsResponse(questions=chatbot_service.questions)


@app.put(
    "/questions",
    response_model=StatusResponse,
    tags=["Questions (global)"],
    summary="Replace default question set",
    description=(
        "Replaces the in-memory default question set used by sessions that have no `survey_id`. "
        "Changes are **not persisted** — use `POST /surveys` for durable, shareable surveys."
    ),
)
def set_questions(payload: SetQuestionsRequest) -> StatusResponse:
    chatbot_service.set_questions(payload.questions)
    return StatusResponse(status="ok", total=len(payload.questions))


# ── Surveys ───────────────────────────────────────────────────────────────────

@app.post(
    "/surveys",
    response_model=SurveyResponse,
    status_code=201,
    tags=["Surveys"],
    summary="Create a new survey",
    description=(
        "Persists a versioned survey with its own question set and returns a shareable `survey_url`. "
        "Employees open that URL to start a session scoped to this specific survey."
    ),
)
def create_survey(payload: CreateSurveyRequest) -> SurveyResponse:
    return chatbot_service.create_survey(questions=payload.questions, title=payload.title, company_name=payload.company_name)


@app.get(
    "/surveys/{survey_id}",
    response_model=SurveyResponse,
    tags=["Surveys"],
    summary="Get survey metadata",
    description="Returns metadata for a survey (title, total questions, creation date, shareable URL). Does not include question details — use `GET /surveys/{survey_id}/questions` for that.",
)
def get_survey(survey_id: str) -> SurveyResponse:
    return chatbot_service.get_survey(survey_id)


# ── Survey questions CRUD ─────────────────────────────────────────────────────

@app.get(
    "/surveys/{survey_id}/questions",
    response_model=QuestionListResponse,
    tags=["Survey Questions"],
    summary="List all questions in a survey",
    description="Returns the ordered list of questions belonging to this survey.",
)
def list_survey_questions(survey_id: str) -> QuestionListResponse:
    return chatbot_service.list_survey_questions(survey_id)


@app.post(
    "/surveys/{survey_id}/questions",
    response_model=QuestionListResponse,
    status_code=201,
    tags=["Survey Questions"],
    summary="Append a question to a survey",
    description="Appends a new question to the end of the survey's question list and returns the updated full list.",
)
def add_survey_question(survey_id: str, question: Question) -> QuestionListResponse:
    return chatbot_service.add_survey_question(survey_id, question)



# ── Survey responses (aggregated) ─────────────────────────────────────────────

@app.get(
    "/surveys/{survey_id}/responses",
    response_model=SurveyResponsesResponse,
    tags=["Survey Responses"],
    summary="Aggregate all responses for a survey",
    description=(
        "Returns every employee session linked to this survey, including their answers. "
        "Includes both in-progress and completed sessions."
    ),
)
def get_survey_responses(survey_id: str) -> SurveyResponsesResponse:
    return chatbot_service.get_survey_responses(survey_id)


# ── Sessions ──────────────────────────────────────────────────────────────────

@app.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=201,
    tags=["Sessions"],
    summary="Start a new employee session",
    description=(
        "Creates a new chat session. If `survey_id` is provided the session is scoped to that survey's question set; "
        "otherwise it uses the default in-memory question set. Returns the full session state including the first assistant message."
    ),
)
def create_session(payload: CreateSessionRequest) -> SessionResponse:
    return chatbot_service.create_session(employee_id=payload.employee_id, survey_id=payload.survey_id)


@app.get(
    "/sessions/{session_id}",
    response_model=SessionResponse,
    tags=["Sessions"],
    summary="Get current session state",
    description="Returns the full session state (chat history, progress, current question) without advancing the conversation.",
)
def get_session(session_id: str) -> SessionResponse:
    return chatbot_service.get_session(session_id=session_id)


@app.post(
    "/sessions/{session_id}/message",
    response_model=SessionResponse,
    tags=["Sessions"],
    summary="Submit an employee message",
    description=(
        "Sends the employee's message to the LLM pipeline: intent is analysed, the answer is extracted and validated, "
        "the response is stored, and the chatbot advances to the next question. Returns the updated session state."
    ),
)
def submit_message(session_id: str, payload: ChatRequest) -> SessionResponse:
    return chatbot_service.submit_message(session_id=session_id, message=payload.message)


@app.get(
    "/sessions/{session_id}/responses",
    tags=["Sessions"],
    summary="Get responses for a single session",
    description="Returns only the recorded answers for this session, without the full chat history.",
)
def get_session_responses(session_id: str) -> dict:
    return chatbot_service.get_responses(session_id=session_id)


@app.delete(
    "/sessions/{session_id}",
    response_model=DeleteResponse,
    tags=["Sessions"],
    summary="Delete a session",
    description="Permanently deletes the session and all its stored responses.",
)
def reset_session(session_id: str) -> DeleteResponse:
    return chatbot_service.reset_session(session_id=session_id)
