from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


QuestionType = Literal[
    "rating",
    "distribution",
    "hours_distribution",
    "single_selection",
    "multiple_selection",
    "number",
    "percentage",
    "free_text",
]


# ── Core question model ───────────────────────────────────────────────────────

class Question(BaseModel):
    """A single survey question with its validation rules."""

    id: str = Field(description="Unique question identifier, e.g. 'q01'")
    category: str = Field(description="Thematic category, e.g. 'Work-Life Balance'")
    question_type: QuestionType = Field(description="Determines how the chatbot validates the answer")
    prompt: str = Field(description="Full question text shown to the employee (may include embedded options)")
    expected_format: str = Field(default="", description="Deprecated — kept for backward compatibility, no longer shown")
    options: list[str] = Field(default_factory=list, description="Category labels (selection / distribution types)")
    min_value: float | None = Field(default=None, description="Minimum allowed numeric value (number / rating types)")
    max_value: float | None = Field(default=None, description="Maximum allowed numeric value (number / rating types)")
    max_choices: int | None = Field(default=None, description="Max selections allowed (multiple_selection type)")
    min_length: int = Field(default=2, description="Minimum character count required (free_text type)")


class PublicQuestion(BaseModel):
    """Question fields exposed to the Streamlit frontend during a session."""

    id: str
    number: int = Field(description="1-based position in the survey")
    total: int = Field(description="Total number of questions in this survey")
    category: str
    question_type: QuestionType
    prompt: str
    options: list[str] = Field(default_factory=list)
    min_value: float | None = None
    max_value: float | None = None
    max_choices: int | None = None
    min_length: int = 2


# ── Chat / session models ─────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: Literal["assistant", "user"]
    content: str


class CreateSessionRequest(BaseModel):
    employee_id: str | None = Field(default=None, description="Optional employee identifier or name")
    survey_id: str | None = Field(default=None, description="UUID of the survey to use; omit to use the default question set")


class ChatRequest(BaseModel):
    message: str = Field(description="Free-text message from the employee")


class SessionResponse(BaseModel):
    """Full session state returned after every API call."""

    session_id: str
    completed: bool = Field(description="True once the employee has answered all questions")
    progress: int = Field(description="Number of questions answered so far")
    total_questions: int
    assistant_message: str = Field(description="The latest message from the chatbot to display")
    current_question: PublicQuestion | None = Field(description="Question the employee is currently on; null when completed")
    chat_history: list[ChatMessage]
    responses: dict[str, Any] = Field(default_factory=dict, description="Map of question_id → recorded response")


# ── Survey models ─────────────────────────────────────────────────────────────

class CreateSurveyRequest(BaseModel):
    """Payload sent by the React generator to create a new versioned survey."""

    questions: list[Question] = Field(description="Ordered list of questions for this survey")
    title: str | None = Field(default=None, description="Optional human-readable survey title")
    company_name: str | None = Field(default=None, description="Optional company or organisation name")


class SurveyRecord(BaseModel):
    """Internal storage format for a survey (persisted to disk)."""

    survey_id: str
    title: str | None = None
    company_name: str | None = None
    questions: list[Question]
    created_at: str


class SurveyResponse(BaseModel):
    """Public survey metadata returned by the API."""

    survey_id: str = Field(description="UUID identifying this survey version")
    title: str | None = None
    company_name: str | None = None
    total_questions: int
    created_at: str = Field(description="ISO-8601 creation timestamp (UTC)")
    survey_url: str = Field(description="Shareable URL employees open to start the survey")


class QuestionListResponse(BaseModel):
    """Questions belonging to a survey."""

    survey_id: str
    questions: list[Question]


class QuestionUpdateResponse(BaseModel):
    """Single updated question within a survey."""

    survey_id: str
    question: Question


class QuestionCountResponse(BaseModel):
    """Confirms how many questions remain after a mutation."""

    survey_id: str
    total: int


class SessionSummary(BaseModel):
    """Lightweight view of one respondent's session."""

    session_id: str
    employee_id: str | None
    completed: bool
    progress: int
    started_at: str | None
    updated_at: str | None
    responses: dict[str, Any] = Field(default_factory=dict)


class SurveyResponsesResponse(BaseModel):
    """Aggregated responses across all employee sessions for a survey."""

    survey_id: str
    total_respondents: int = Field(description="Number of sessions that started this survey")
    completed_count: int = Field(description="Number of sessions that completed all questions")
    sessions: list[SessionSummary]


# ── Global question list ──────────────────────────────────────────────────────

class SetQuestionsRequest(BaseModel):
    questions: list[Question]


class GlobalQuestionsResponse(BaseModel):
    questions: list[Question]


# ── Misc ──────────────────────────────────────────────────────────────────────

class DeleteResponse(BaseModel):
    status: Literal["deleted"]


class StatusResponse(BaseModel):
    status: Literal["ok"]
    total: int


class LabeledDistributionEntry(BaseModel):
    label: str
    percentage: float


class HoursDistributionData(BaseModel):
    hours_per_week: float
    individual_work_pct: float
    collaborative_work_pct: float
    other_pct: float


class ExtractedAnswer(BaseModel):
    rating: int | None = None
    number: float | None = None
    percentage: float | None = None
    coded_distribution: dict[str, float] | None = None
    labeled_distribution: list[LabeledDistributionEntry] | None = None
    hours_distribution: HoursDistributionData | None = None
    single_selection: str | None = None
    multiple_selection: list[str] | None = None
    free_text: str | None = None


class ValidationResult(BaseModel):
    valid: bool
    normalized_answer: Any | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok"]
