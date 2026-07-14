from __future__ import annotations

import os
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from sqlalchemy import Boolean, Float, Integer, String, Text, UniqueConstraint, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, scoped_session, sessionmaker

# ── Database connection ───────────────────────────────────────────────────────

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgresokay:postgres@localhost:5432/survey")

_engine = create_engine(DATABASE_URL, pool_pre_ping=True, echo=False)
_Session = scoped_session(sessionmaker(bind=_engine))


# ── ORM table definitions ─────────────────────────────────────────────────────

class _Base(DeclarativeBase):
    pass


class _SurveyRow(_Base):
    """
    surveys
    One row = one survey deployment created by the admin.
    """
    __tablename__ = "surveys"

    survey_id:    Mapped[str]      = mapped_column(String(36), primary_key=True)
    title:        Mapped[str|None] = mapped_column(Text, nullable=True)
    company_name: Mapped[str|None] = mapped_column(Text, nullable=True)
    created_at:   Mapped[str]      = mapped_column(String(50), nullable=False)


class _QuestionRow(_Base):
    """
    questions
    One row = one question belonging to a survey.
    question_id is a UUID PK — unique across all surveys.
    question_key is the logical ID (e.g. 'q01') scoped within the survey.
    """
    __tablename__ = "questions"

    question_id:       Mapped[str]      = mapped_column(String(36), primary_key=True)    # UUID
    question_key:      Mapped[str]      = mapped_column(String(36), nullable=False)       # e.g. 'q01'
    survey_id:         Mapped[str]      = mapped_column(String(36), nullable=False, index=True)
    position:          Mapped[int]      = mapped_column(Integer, nullable=False)
    category:          Mapped[str]      = mapped_column(Text, nullable=False)
    question_type:     Mapped[str]      = mapped_column(String(30), nullable=False)
    prompt:            Mapped[str]      = mapped_column(Text, nullable=False)
    expected_format:   Mapped[str]      = mapped_column(Text, nullable=False)
    options:           Mapped[list]     = mapped_column(JSONB, nullable=False)
    min_value:         Mapped[float|None] = mapped_column(Float, nullable=True)
    max_value:         Mapped[float|None] = mapped_column(Float, nullable=True)
    max_choices:       Mapped[int|None] = mapped_column(Integer, nullable=True)
    min_length:        Mapped[int]      = mapped_column(Integer, nullable=False, default=2)
    distribution_mode: Mapped[str|None] = mapped_column(String(10), nullable=True)


class _EmployeeRow(_Base):
    """
    employees
    One row = one person taking a specific survey.
    Tracks the full chat session state for that employee.
    Name is optional — the employee can stay anonymous.
    """
    __tablename__ = "employees"

    employee_id:   Mapped[str]      = mapped_column(String(36), primary_key=True)   # UUID
    survey_id:     Mapped[str|None] = mapped_column(String(36), nullable=True, index=True)   # FK → surveys
    name:          Mapped[str|None] = mapped_column(Text, nullable=True)             # what the employee typed
    created_at:    Mapped[str]      = mapped_column(String(50), nullable=False)
    updated_at:    Mapped[str]      = mapped_column(String(50), nullable=False)
    current_index: Mapped[int]      = mapped_column(Integer, nullable=False, default=0)
    completed:     Mapped[bool]     = mapped_column(Boolean, nullable=False, default=False)
    editing:       Mapped[dict|None]= mapped_column(JSONB, nullable=True)            # non-null only during edit
    chat_history:  Mapped[list]     = mapped_column(JSONB, nullable=False)           # list[{role, content}]


class _ResponseRow(_Base):
    """
    responses
    One row = one employee's answer to one question.
    The composite unique constraint ensures each (employee, question) pair has at most one answer
    (editing overwrites the existing row rather than inserting a duplicate).
    """
    __tablename__ = "responses"
    __table_args__ = (
        UniqueConstraint("employee_id", "question_id", name="uq_employee_question"),
    )

    response_id:   Mapped[str] = mapped_column(String(36), primary_key=True)        # UUID
    survey_id:     Mapped[str] = mapped_column(String(36), nullable=False, index=True)   # FK → surveys
    question_id:   Mapped[str] = mapped_column(String(36), nullable=False, index=True)   # FK → questions
    employee_id:   Mapped[str] = mapped_column(String(36), nullable=False, index=True)   # FK → employees
    question_type: Mapped[str] = mapped_column(String(30), nullable=False)
    raw_answer:    Mapped[str] = mapped_column(Text, nullable=False)                 # what the employee typed
    result:        Mapped[dict]= mapped_column(JSONB, nullable=False)                # validated, typed result
    answered_at:   Mapped[str] = mapped_column(String(50), nullable=False)


def init_db() -> None:
    """Create all tables if they do not exist. Called once on application startup."""
    _Base.metadata.create_all(_engine)


# ── Store protocols ───────────────────────────────────────────────────────────
#
# chatbot.py depends only on these protocols — never on the concrete classes.
# To switch databases (e.g. to Go + GORM), only the classes below change.

@runtime_checkable
class SessionStore(Protocol):
    def save(self, session_id: str, payload: dict[str, Any]) -> None: ...
    def load(self, session_id: str) -> dict[str, Any] | None: ...
    def delete(self, session_id: str) -> bool: ...
    def list_by_survey(self, survey_id: str) -> list[dict[str, Any]]: ...


@runtime_checkable
class SurveyStore(Protocol):
    def save(self, survey_id: str, payload: dict[str, Any]) -> None: ...
    def load(self, survey_id: str) -> dict[str, Any] | None: ...


# ── PostgreSQL implementations ─────────────────────────────────────────────────

class PgSessionStore:
    """
    Reads and writes employee sessions across two tables:
      - employees  → session state (current_index, completed, editing, chat_history)
      - responses  → one row per answered question (the actual survey data)

    chatbot.py works with a flat session dict that includes 'responses' inline.
    This class assembles that dict on load and splits it on save.
    """

    def save(self, session_id: str, payload: dict[str, Any]) -> None:
        db = _Session()

        # ── Upsert the employee row ───────────────────────────────────────────
        emp = db.get(_EmployeeRow, session_id)
        if emp:
            emp.survey_id     = payload.get("survey_id")
            emp.name          = payload.get("employee_id")   # "employee_id" in the dict = the name they typed
            emp.updated_at    = payload.get("updated_at", "")
            emp.current_index = int(payload.get("current_index", 0))
            emp.completed     = bool(payload.get("completed", False))
            emp.editing       = payload.get("editing")
            emp.chat_history  = payload.get("chat_history", [])
        else:
            emp = _EmployeeRow(
                employee_id   = session_id,
                survey_id     = payload.get("survey_id"),
                name          = payload.get("employee_id"),
                created_at    = payload.get("created_at", ""),
                updated_at    = payload.get("updated_at", ""),
                current_index = int(payload.get("current_index", 0)),
                completed     = bool(payload.get("completed", False)),
                editing       = payload.get("editing"),
                chat_history  = payload.get("chat_history", []),
            )
            db.add(emp)

        # ── Upsert individual response rows ───────────────────────────────────
        for question_id, resp in payload.get("responses", {}).items():
            existing = (
                db.query(_ResponseRow)
                .filter_by(employee_id=session_id, question_id=question_id)
                .first()
            )
            if existing:
                existing.result      = resp.get("response", resp.get("result", {}))
                existing.raw_answer  = resp.get("raw_answer", "")
                existing.answered_at = resp.get("answered_at", "")
            else:
                from uuid import uuid4
                db.add(_ResponseRow(
                    response_id   = str(uuid4()),
                    survey_id     = payload.get("survey_id", ""),
                    question_id   = question_id,
                    employee_id   = session_id,
                    question_type = resp.get("question_type", ""),
                    raw_answer    = resp.get("raw_answer", ""),
                    result        = resp.get("response", resp.get("result", {})),
                    answered_at   = resp.get("answered_at", ""),
                ))

        db.commit()

    def load(self, session_id: str) -> dict[str, Any] | None:
        db = _Session()
        emp = db.get(_EmployeeRow, session_id)
        if emp is None:
            return None
        responses = db.query(_ResponseRow).filter_by(employee_id=session_id).all()
        return _build_session_dict(emp, responses)

    def delete(self, session_id: str) -> bool:
        db = _Session()
        emp = db.get(_EmployeeRow, session_id)
        if emp is None:
            return False
        db.query(_ResponseRow).filter_by(employee_id=session_id).delete()
        db.delete(emp)
        db.commit()
        return True

    def list_by_survey(self, survey_id: str) -> list[dict[str, Any]]:
        db = _Session()
        employees = db.query(_EmployeeRow).filter_by(survey_id=survey_id).all()
        result = []
        for emp in employees:
            responses = db.query(_ResponseRow).filter_by(employee_id=emp.employee_id).all()
            result.append(_build_session_dict(emp, responses))
        return result


class PgSurveyStore:
    """
    Reads and writes surveys across two tables:
      - surveys    → title + metadata
      - questions  → one row per question, ordered by position

    chatbot.py works with a survey dict that has 'questions' as an inline list.
    This class assembles that dict on load and splits it on save.
    """

    def save(self, survey_id: str, payload: dict[str, Any]) -> None:
        db = _Session()

        # ── Upsert survey row ─────────────────────────────────────────────────
        survey = db.get(_SurveyRow, survey_id)
        if survey:
            survey.title        = payload.get("title")
            survey.company_name = payload.get("company_name")
        else:
            db.add(_SurveyRow(
                survey_id    = survey_id,
                title        = payload.get("title"),
                company_name = payload.get("company_name"),
                created_at   = payload.get("created_at", ""),
            ))

        # ── Replace all questions for this survey ─────────────────────────────
        db.query(_QuestionRow).filter_by(survey_id=survey_id).delete()
        for position, q in enumerate(payload.get("questions", [])):
            is_dict = isinstance(q, dict)
            db.add(_QuestionRow(
                question_id       = str(uuid4()),
                question_key      = q.get("id", "") if is_dict else q.id,
                survey_id         = survey_id,
                position          = position,
                category          = q.get("category", "") if is_dict else q.category,
                question_type     = q.get("question_type", "") if is_dict else q.question_type,
                prompt            = q.get("prompt", "") if is_dict else q.prompt,
                expected_format   = q.get("expected_format", "") if is_dict else q.expected_format,
                options           = q.get("options", []) if is_dict else q.options,
                min_value         = q.get("min_value") if is_dict else q.min_value,
                max_value         = q.get("max_value") if is_dict else q.max_value,
                max_choices       = q.get("max_choices") if is_dict else q.max_choices,
                min_length        = q.get("min_length", 2) if is_dict else q.min_length,
                distribution_mode = q.get("distribution_mode") if is_dict else None,
            ))

        db.commit()

    def load(self, survey_id: str) -> dict[str, Any] | None:
        db = _Session()
        survey = db.get(_SurveyRow, survey_id)
        if survey is None:
            return None
        questions = (
            db.query(_QuestionRow)
            .filter_by(survey_id=survey_id)
            .order_by(_QuestionRow.position)
            .all()
        )
        return {
            "survey_id":    survey.survey_id,
            "title":        survey.title,
            "company_name": survey.company_name,
            "created_at":   survey.created_at,
            "questions":    [_question_row_to_dict(q) for q in questions],
        }


# ── Private helpers ────────────────────────────────────────────────────────────

def _build_session_dict(emp: _EmployeeRow, responses: list[_ResponseRow]) -> dict[str, Any]:
    """Assembles the flat session dict that chatbot.py works with."""
    responses_map = {
        r.question_id: {
            "question_id":   r.question_id,
            "question_type": r.question_type,
            "raw_answer":    r.raw_answer,
            "response":      r.result,
            "answered_at":   r.answered_at,
        }
        for r in responses
    }
    return {
        "session_id":    emp.employee_id,
        "survey_id":     emp.survey_id,
        "employee_id":   emp.name,         # the name they typed, surfaced as employee_id in API
        "created_at":    emp.created_at,
        "updated_at":    emp.updated_at,
        "current_index": emp.current_index,
        "completed":     emp.completed,
        "editing":       emp.editing,
        "chat_history":  emp.chat_history or [],
        "responses":     responses_map,
    }


def _question_row_to_dict(q: _QuestionRow) -> dict[str, Any]:
    return {
        "id":               q.question_key,
        "category":         q.category,
        "question_type":    q.question_type,
        "prompt":           q.prompt,
        "expected_format":  q.expected_format,
        "options":          q.options or [],
        "min_value":        q.min_value,
        "max_value":        q.max_value,
        "max_choices":      q.max_choices,
        "min_length":       q.min_length,
        "distribution_mode": q.distribution_mode,
    }
