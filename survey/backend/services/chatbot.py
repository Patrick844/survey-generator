from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status

from backend.models import ChatMessage, PublicQuestion, Question, SessionResponse, SurveyRecord, SurveyResponse
from backend.services.ai_service import SurveyAIService
from backend.services.storage import PgSessionStore, PgSurveyStore, SessionStore, SurveyStore


class SurveyChatbotService:
    def __init__(
        self,
        store: SessionStore | None = None,
        survey_store: SurveyStore | None = None,
        ai_service: SurveyAIService | None = None,
    ) -> None:
        self.store: SessionStore = store or PgSessionStore()
        self.survey_store: SurveyStore = survey_store or PgSurveyStore()
        self.ai_service = ai_service or SurveyAIService()
        self.questions: list[Question] = []
        self._frontend_url = os.getenv("FRONTEND_URL", "http://localhost:8501")

    def set_questions(self, questions: list[Question]) -> None:
        self.questions = questions
        print(f"\n[CONFIG] Questions updated — {len(questions)} questions loaded")
        for i, q in enumerate(questions, 1):
            print(f"  Q{i:02d} [{q.question_type}] {q.id} — {q.prompt[:60]}")
        print()

    def create_survey(self, questions: list[Question], title: str | None = None, company_name: str | None = None) -> SurveyResponse:
        survey_id = str(uuid4())
        now = datetime.now(UTC).isoformat()
        record = SurveyRecord(
            survey_id=survey_id,
            title=title,
            company_name=company_name,
            questions=questions,
            created_at=now,
        )
        self.survey_store.save(survey_id, record.model_dump())
        print(f"\n[SURVEY] Created survey {survey_id} — {len(questions)} questions")
        return SurveyResponse(
            survey_id=survey_id,
            title=title,
            company_name=company_name,
            total_questions=len(questions),
            created_at=now,
            survey_url=f"{self._frontend_url}?survey_id={survey_id}",
        )

    def get_survey(self, survey_id: str) -> SurveyResponse:
        record = self.survey_store.load(survey_id)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Survey not found")
        return SurveyResponse(
            survey_id=record["survey_id"],
            title=record.get("title"),
            company_name=record.get("company_name"),
            total_questions=len(record["questions"]),
            created_at=record["created_at"],
            survey_url=f"{self._frontend_url}?survey_id={survey_id}",
        )

    def create_session(self, employee_id: str | None = None, survey_id: str | None = None) -> SessionResponse:
        if survey_id:
            record = self.survey_store.load(survey_id)
            if record is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Survey not found")
            questions = [Question(**q) for q in record["questions"]]
        else:
            questions = self.questions

        session_id = str(uuid4())
        now = datetime.now(UTC).isoformat()
        first_question = questions[0]

        print(f"\n{'#'*60}")
        print(f"[SESSION] New session created: {session_id}")
        print(f"[SESSION] Employee: {employee_id or 'anonymous'}")
        print(f"[SESSION] Survey: {survey_id or 'default'}")
        print(f"[SESSION] Starting with Q1/{len(questions)}: {first_question.id} ({first_question.question_type})")
        print(f"{'#'*60}\n")

        assistant_message = self.ai_service.question_message(
            first_question,
            number=1,
            total=len(questions),
            greeting=True,
        )

        session = {
            "session_id": session_id,
            "survey_id": survey_id,
            "employee_id": employee_id,
            "created_at": now,
            "updated_at": now,
            "current_index": 0,
            "completed": False,
            "editing": None,
            "responses": {},
            "chat_history": [
                {"role": "assistant", "content": assistant_message},
            ],
        }
        self.store.save(session_id, session)
        return self._to_response(session, assistant_message=assistant_message)

    def get_session(self, session_id: str) -> SessionResponse:
        session = self._load_session_or_404(session_id)
        last_assistant_message = self._last_assistant_message(session)
        return self._to_response(session, assistant_message=last_assistant_message)

    def submit_message(self, session_id: str, message: str) -> SessionResponse:
        session = self._load_session_or_404(session_id)
        session["chat_history"].append({"role": "user", "content": message})
        questions = self._get_questions(session)

        current_question, current_number = self._current_question_and_number(session, questions)
        analysis = self.ai_service.analyze_user_message(
            user_message=message,
            current_question=current_question,
            current_question_number=current_number,
            total_questions=len(questions),
            completed=bool(session.get("completed", False)),
            editing=session.get("editing"),
            responses=session.get("responses", {}),
        )

        if analysis.intent == "go_to_question":
            if analysis.question_number is None:
                assistant_message = self.ai_service.unknown_message(
                    question=current_question,
                    number=current_number,
                    total=len(questions),
                )
                return self._append_save_respond(session, assistant_message)
            return self._go_to_question(session=session, questions=questions, target_index=analysis.question_number - 1)

        if analysis.intent == "previous_question":
            target_index = max(0, int(session.get("current_index", 0)) - 1)
            return self._go_to_question(session=session, questions=questions, target_index=target_index)

        if analysis.intent == "show_progress":
            assistant_message = self.ai_service.progress_message(
                answered=len(session.get("responses", {})),
                total=len(questions),
                completed=bool(session.get("completed", False)),
            )
            return self._append_save_respond(session, assistant_message)

        if analysis.intent == "help":
            assistant_message = self.ai_service.help_message(
                question=current_question,
                number=current_number,
                total=len(questions),
            )
            return self._append_save_respond(session, assistant_message)

        if analysis.intent == "cancel_edit":
            assistant_message = self._cancel_editing(session=session, questions=questions)
            return self._append_save_respond(session, assistant_message)

        if analysis.intent == "unknown":
            assistant_message = self.ai_service.unknown_message(
                question=current_question,
                number=current_number,
                total=len(questions),
            )
            return self._append_save_respond(session, assistant_message)

        if session["completed"]:
            assistant_message = (
                "Your survey is already complete. "
                "If you want to edit a previous answer, say something like: `go back to question 1`."
            )
            return self._append_save_respond(session, assistant_message)

        question = questions[session["current_index"]]
        extracted = analysis.extracted_answer

        answered_so_far = len(session.get("responses", {}))
        print(f"\n{'='*60}")
        print(f"[SURVEY]  Session  : {session_id}")
        print(f"[SURVEY]  Progress : {answered_so_far}/{len(questions)} answered")
        print(f"[SURVEY]  Question : {question.id} ({question.question_type}) — Q{session['current_index'] + 1}/{len(questions)}")
        print(f"[SURVEY]  Category : {question.category}")
        print(f"[INPUT]   Message  : {message!r}")
        print(f"[LLM]     Intent   : {analysis.intent}  confidence={analysis.confidence:.2f}")
        print(f"[LLM]     Extracted: {extracted.model_dump() if extracted is not None else 'None'}")
        print(f"{'='*60}")

        if extracted is None:
            result_obj = None
        else:
            result_obj = self.ai_service.evaluate_answer(extracted=extracted, question=question)

        if result_obj is None:
            print(f"[VALIDATE] SKIP — LLM could not extract a structured answer")
        else:
            status = "PASS" if result_obj.valid else "FAIL"
            print(f"[VALIDATE] {status} | error={result_obj.error!r}")
            if result_obj.valid:
                print(f"[SAVE]    Storing answer for {question.id}: {result_obj.normalized_answer!r}")
        print(f"{'='*60}\n")

        if result_obj is None or not result_obj.valid:
            error = (result_obj.error if result_obj else None) or "I couldn't understand your answer. Please try again using the expected format."
            assistant_message = self.ai_service.invalid_message(
                error=error,
                question=question,
                user_answer=message,
                normalized_answer=None,
            )
            return self._append_save_respond(session, assistant_message)

        session["responses"][question.id] = {
            "question_id": question.id,
            "question_number": session["current_index"] + 1,
            "category": question.category,
            "question_type": question.question_type,
            "question_text": question.prompt,
            "raw_answer": message,
            "response": self._build_response(result_obj.normalized_answer, question.question_type),
            "answered_at": datetime.now(UTC).isoformat(),
        }

        editing = session.get("editing")
        if editing:
            assistant_message = self._finish_editing(session=session, questions=questions)
        else:
            assistant_message = self._move_to_next_question(
                session=session,
                questions=questions,
                user_message=message,
                validated_answer=result_obj.normalized_answer,
            )

        return self._append_save_respond(session, assistant_message)

    def get_responses(self, session_id: str) -> dict[str, Any]:
        session = self._load_session_or_404(session_id)
        questions = self._get_questions(session)
        return {
            "session_id": session_id,
            "survey_id": session.get("survey_id"),
            "employee_id": session.get("employee_id"),
            "completed": session["completed"],
            "progress": len(session["responses"]),
            "total_questions": len(questions),
            "responses": session["responses"],
        }

    def reset_session(self, session_id: str) -> dict[str, str]:
        deleted = self.store.delete(session_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        return {"status": "deleted"}

    # ── Survey CRUD ───────────────────────────────────────────────────────────

    def list_survey_questions(self, survey_id: str) -> dict[str, Any]:
        record = self._load_survey_or_404(survey_id)
        return {"survey_id": survey_id, "questions": record["questions"]}

    def add_survey_question(self, survey_id: str, question: Question) -> dict[str, Any]:
        record = self._load_survey_or_404(survey_id)
        record["questions"].append(question.model_dump())
        self.survey_store.save(survey_id, record)
        return {"survey_id": survey_id, "total": len(record["questions"]), "questions": record["questions"]}

    def update_survey_question(self, survey_id: str, question_id: str, question: Question) -> dict[str, Any]:
        record = self._load_survey_or_404(survey_id)
        idx = next((i for i, q in enumerate(record["questions"]) if q["id"] == question_id), None)
        if idx is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
        record["questions"][idx] = question.model_dump()
        self.survey_store.save(survey_id, record)
        return {"survey_id": survey_id, "question": record["questions"][idx]}

    def delete_survey_question(self, survey_id: str, question_id: str) -> dict[str, Any]:
        record = self._load_survey_or_404(survey_id)
        before = len(record["questions"])
        record["questions"] = [q for q in record["questions"] if q["id"] != question_id]
        if len(record["questions"]) == before:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
        self.survey_store.save(survey_id, record)
        return {"survey_id": survey_id, "total": len(record["questions"])}

    # ── Survey responses (aggregated across all sessions) ─────────────────────

    def get_survey_responses(self, survey_id: str) -> dict[str, Any]:
        self._load_survey_or_404(survey_id)
        sessions = self.store.list_by_survey(survey_id)
        aggregated = [
            {
                "session_id":  s["session_id"],
                "employee_id": s.get("employee_id"),
                "completed":   s.get("completed", False),
                "progress":    len(s.get("responses", {})),
                "responses":   s.get("responses", {}),
                "started_at":  s.get("created_at"),
                "updated_at":  s.get("updated_at"),
            }
            for s in sessions
        ]
        return {
            "survey_id":         survey_id,
            "total_respondents": len(aggregated),
            "completed_count":   sum(1 for s in aggregated if s["completed"]),
            "sessions":          aggregated,
        }

    def _load_survey_or_404(self, survey_id: str) -> dict[str, Any]:
        record = self.survey_store.load(survey_id)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Survey not found")
        return record

    def _get_questions(self, session: dict[str, Any]) -> list[Question]:
        survey_id = session.get("survey_id")
        if survey_id:
            record = self.survey_store.load(survey_id)
            if record:
                return [Question(**q) for q in record["questions"]]
        return self.questions

    def _go_to_question(self, session: dict[str, Any], questions: list[Question], target_index: int) -> SessionResponse:
        if target_index < 0 or target_index >= len(questions):
            assistant_message = f"I couldn't find question {target_index + 1}. Please choose a question between 1 and {len(questions)}."
            return self._append_save_respond(session, assistant_message)

        original_current_index = int(session.get("current_index", 0))
        was_completed = bool(session.get("completed", False))
        question = questions[target_index]
        existing_response = session.get("responses", {}).get(question.id)
        previous_answer = existing_response.get("raw_answer") if existing_response else "No previous answer saved yet."

        session["editing"] = {
            "target_index": target_index,
            "return_index": original_current_index,
            "was_completed": was_completed,
        }
        session["current_index"] = target_index
        session["completed"] = False

        assistant_message = self.ai_service.edit_start_message(
            question,
            number=target_index + 1,
            total=len(questions),
            previous_answer=previous_answer,
        )
        return self._append_save_respond(session, assistant_message)

    def _finish_editing(self, session: dict[str, Any], questions: list[Question]) -> str:
        editing = session.get("editing") or {}
        return_index = int(editing.get("return_index", session.get("current_index", 0)))
        was_completed = bool(editing.get("was_completed", False))
        session["editing"] = None

        if was_completed:
            session["current_index"] = len(questions)
            session["completed"] = True
            return self.ai_service.edit_saved_message(
                return_question=None,
                return_number=None,
                total=len(questions),
                completed=True,
            )

        session["completed"] = False
        session["current_index"] = min(return_index, len(questions) - 1)
        return_question = questions[session["current_index"]]
        return_number = session["current_index"] + 1
        return self.ai_service.edit_saved_message(
            return_question=return_question,
            return_number=return_number,
            total=len(questions),
            completed=False,
        )

    def _cancel_editing(self, session: dict[str, Any], questions: list[Question]) -> str:
        editing = session.get("editing")
        if not editing:
            current_question, current_number = self._current_question_and_number(session, questions)
            return self.ai_service.help_message(
                question=current_question,
                number=current_number,
                total=len(questions),
            )

        return_index = int(editing.get("return_index", 0))
        was_completed = bool(editing.get("was_completed", False))
        session["editing"] = None
        session["completed"] = was_completed
        session["current_index"] = len(questions) if was_completed else min(return_index, len(questions) - 1)

        if was_completed:
            return "Edit cancelled. Your survey is still complete."

        question = questions[session["current_index"]]
        return "Edit cancelled.\n\n" + self.ai_service.question_message(
            question,
            number=session["current_index"] + 1,
            total=len(questions),
        )

    def _move_to_next_question(
        self,
        session: dict[str, Any],
        questions: list[Question],
        user_message: str,
        validated_answer: object,
    ) -> str:
        session["current_index"] += 1

        if session["current_index"] >= len(questions):
            session["completed"] = True
            answered = len(session.get("responses", {}))
            print(f"\n{'#'*60}")
            print(f"[SURVEY]  COMPLETED — session {session['session_id']}")
            print(f"[SURVEY]  {answered}/{len(questions)} questions answered")
            print(f"{'#'*60}\n")
            return self.ai_service.completed_message(
                user_message=user_message,
                validated_answer=validated_answer,
            )

        next_question = questions[session["current_index"]]
        return self.ai_service.accepted_then_next_message(
            next_question,
            number=session["current_index"] + 1,
            total=len(questions),
            user_message=user_message,
            validated_answer=validated_answer,
        )

    def _current_question_and_number(self, session: dict[str, Any], questions: list[Question]) -> tuple[Question | None, int | None]:
        if session.get("completed", False):
            return None, None
        current_index = min(int(session.get("current_index", 0)), len(questions) - 1)
        return questions[current_index], current_index + 1

    def _append_save_respond(self, session: dict[str, Any], assistant_message: str) -> SessionResponse:
        session["chat_history"].append({"role": "assistant", "content": assistant_message})
        self._touch_and_save(session)
        return self._to_response(session, assistant_message=assistant_message)

    def _load_session_or_404(self, session_id: str) -> dict[str, Any]:
        session = self.store.load(session_id)
        if session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        session.setdefault("editing", None)
        session.setdefault("responses", {})
        session.setdefault("chat_history", [])
        return session

    def _touch_and_save(self, session: dict[str, Any]) -> None:
        session["updated_at"] = datetime.now(UTC).isoformat()
        self.store.save(session["session_id"], session)

    def _to_response(self, session: dict[str, Any], assistant_message: str) -> SessionResponse:
        questions = self._get_questions(session)
        current_question = None
        if not session["completed"]:
            current_index = min(int(session["current_index"]), len(questions) - 1)
            current_question = self._public_question(
                questions[current_index],
                number=current_index + 1,
                total=len(questions),
            )

        return SessionResponse(
            session_id=session["session_id"],
            completed=session["completed"],
            progress=len(session["responses"]),
            total_questions=len(questions),
            assistant_message=assistant_message,
            current_question=current_question,
            chat_history=[ChatMessage(**item) for item in session["chat_history"]],
            responses=session["responses"],
        )

    def _public_question(self, question: Question, number: int, total: int) -> PublicQuestion:
        return PublicQuestion(
            id=question.id,
            number=number,
            total=total,
            category=question.category,
            question_type=question.question_type,
            prompt=question.prompt,
            expected_format=question.expected_format,
            options=question.options,
            min_value=question.min_value,
            max_value=question.max_value,
            max_choices=question.max_choices,
            min_length=question.min_length,
        )

    def _build_response(self, validated_answer: Any, question_type: str) -> dict[str, Any]:
        if question_type in ("rating", "number", "single_selection", "free_text"):
            return {"value": validated_answer}

        if question_type == "percentage":
            value = validated_answer["value"] if isinstance(validated_answer, dict) else validated_answer
            return {"value": value}

        if question_type == "multiple_selection":
            return {"values": validated_answer}

        if question_type == "distribution":
            if isinstance(validated_answer, list):
                return {"entries": validated_answer}
            return validated_answer  # coded distribution — already {"A": 20, "B": 15, ...}

        if question_type == "hours_distribution":
            return validated_answer  # already {"hours_per_week": ..., "individual_work_percentage": ..., ...}

        return {"value": validated_answer}

    def _last_assistant_message(self, session: dict[str, Any]) -> str:
        for message in reversed(session["chat_history"]):
            if message["role"] == "assistant":
                return str(message["content"])
        return ""
