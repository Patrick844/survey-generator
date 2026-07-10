from __future__ import annotations

from typing import Any

from backend.models import ExtractedAnswer, Question, ValidationResult
from backend.services.llm_service import LLMUserMessageAnalysis, OpenAILLMService
from backend.services.validator import AnswerValidator


class SurveyAIService:
    """
    OpenAI-powered chatbot intelligence layer.

    OpenAI is used for:
    - intent detection
    - natural-language answer normalization
    - chatbot response wording

    A deterministic validator is still used after the LLM so that stored survey
    data remains reliable and format-correct.
    """

    def __init__(self, llm_service: OpenAILLMService | None = None) -> None:
        self.validator = AnswerValidator()
        self.llm = llm_service or OpenAILLMService()

    def analyze_user_message(
        self,
        *,
        user_message: str,
        current_question: Question | None,
        current_question_number: int | None,
        total_questions: int,
        completed: bool,
        editing: dict[str, Any] | None,
        responses: dict[str, Any],
    ) -> LLMUserMessageAnalysis:
        return self.llm.analyze_user_message(
            user_message=user_message,
            current_question=current_question,
            current_question_number=current_question_number,
            total_questions=total_questions,
            completed=completed,
            editing=editing,
            responses=responses,
        )

    def evaluate_answer(self, extracted: ExtractedAnswer, question: Question) -> ValidationResult:
        return self.validator.validate_structured(extracted=extracted, question=question)

    def question_message(self, question: Question, number: int, total: int, *, greeting: bool = False) -> str:
        return self.llm.compose_question_message(question=question, number=number, total=total, greeting=greeting)

    def invalid_message(
        self,
        *,
        error: str,
        question: Question,
        user_answer: str,
        normalized_answer: str | None,
    ) -> str:
        return self.llm.compose_invalid_message(
            error=error,
            question=question,
            user_answer=user_answer,
            normalized_answer=normalized_answer,
        )

    def accepted_then_next_message(
        self,
        next_question: Question,
        number: int,
        total: int,
        user_message: str,
        validated_answer: Any,
    ) -> str:
        return self.llm.compose_accepted_then_next_message(
            next_question=next_question,
            number=number,
            total=total,
            user_message=user_message,
            validated_answer=validated_answer,
        )

    def edit_start_message(self, question: Question, number: int, total: int, previous_answer: str) -> str:
        return self.llm.compose_edit_start_message(
            question=question,
            number=number,
            total=total,
            previous_answer=previous_answer,
        )

    def edit_saved_message(
        self,
        *,
        return_question: Question | None,
        return_number: int | None,
        total: int,
        completed: bool,
    ) -> str:
        return self.llm.compose_edit_saved_message(
            return_question=return_question,
            return_number=return_number,
            total=total,
            completed=completed,
        )

    def completed_message(self, user_message: str, validated_answer: Any) -> str:
        return self.llm.compose_completed_message(
            user_message=user_message,
            validated_answer=validated_answer,
        )

    def help_message(self, *, question: Question | None, number: int | None, total: int) -> str:
        return self.llm.compose_help_message(question=question, number=number, total=total)

    def progress_message(self, *, answered: int, total: int, completed: bool) -> str:
        return self.llm.compose_progress_message(answered=answered, total=total, completed=completed)

    def unknown_message(self, *, question: Question | None, number: int | None, total: int) -> str:
        return self.llm.compose_unknown_message(question=question, number=number, total=total)
