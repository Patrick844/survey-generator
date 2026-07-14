from __future__ import annotations

import os
import re
from typing import Any, Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from backend.models import ExtractedAnswer, HoursDistributionData, LabeledDistributionEntry, Question

load_dotenv()


IntentName = Literal[
    "answer_current_question",
    "go_to_question",
    "previous_question",
    "show_progress",
    "help",
    "cancel_edit",
    "unknown",
]


class LLMUserMessageAnalysis(BaseModel):
    """Structured output returned by OpenAI for every user message."""

    intent: IntentName
    question_number: int | None = Field(
        default=None,
        description="1-based question number when the user wants to go back/edit a specific question.",
    )
    extracted_answer: ExtractedAnswer | None = Field(
        default=None,
        description=(
            "Typed extraction of the user's answer. Only set when intent is answer_current_question. "
            "Populate only the field that matches the current question type; leave all others null."
        ),
    )
    assistant_note: str = Field(default="", description="Short internal note about what the model understood.")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class OpenAILLMService:
    """
    OpenAI-powered language layer.

    The backend uses this layer for:
    - user intent detection
    - answer normalization
    - friendly chatbot wording

    Set OPENAI_FAKE_MODE=true for tests/local demos without calling the API.
    In real usage, set OPENAI_API_KEY and optionally OPENAI_MODEL.
    """

    def __init__(self, model: str | None = None, fake_mode: bool | None = None) -> None:
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.fake_mode = self._env_flag("OPENAI_FAKE_MODE") if fake_mode is None else fake_mode
        self._client: Any | None = None

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
        if self.fake_mode:
            return self._fake_analyze_user_message(
                user_message=user_message,
                current_question=current_question,
                current_question_number=current_question_number,
            )

        system_prompt = """
You are the controller for an employee workplace survey chatbot.

## Step 1 — classify intent
- answer_current_question  → the user is answering the current survey question
- go_to_question           → user mentions a specific question number to edit or jump to (e.g. "go back to question 1", "edit question 5", "change my answer for Q3"). Extract question_number as the EXACT 1-based number they stated. This is ABSOLUTE, never relative to the current position.
- previous_question        → user says "go back", "previous", or "go to previous question" with NO number mentioned
- show_progress            → user asks how many questions are left or answered
- help                     → user asks for the expected format or how to answer
- cancel_edit              → user explicitly wants to cancel an edit in progress
- unknown                  → anything else

IMPORTANT: If the user says "go back to question 1", the intent is go_to_question with question_number=1, NOT previous_question. Only use previous_question when there is no number at all.

## Step 2 — extract the answer (only when intent = answer_current_question)

Populate extracted_answer with the field that matches the current question type.
Leave all other fields null. NEVER invent, add, or complete data the user did not provide.

Rules per type:

- rating          → extracted_answer.rating       = integer the user stated. Null if unclear.
- number          → extracted_answer.number       = numeric value (strip "minutes", "min", etc.). Null if unclear.
- percentage      → extracted_answer.percentage   = numeric value only (no % sign). Null if unclear.
- distribution    → extracted_answer.labeled_distribution = list of {label, percentage} objects,
                    one per category (e.g. "30% work, 70% meetings"). The labels are the question's
                    categories. Use ONLY categories/percentages the user provided; do NOT invent them.
                    If no percentages were given, set labeled_distribution = null.
- single_selection → extracted_answer.single_selection = the option or code the user chose.
- multiple_selection → extracted_answer.multiple_selection = list of options/codes chosen.
- free_text       → extracted_answer.free_text = the user's text verbatim.

When extraction is impossible (answer is incomplete, ambiguous, or missing required data), set extracted_answer = null.
Python validation will reject it and ask the user to resend with the correct format.
""".strip()

        state_payload = {
            "user_message": user_message,
            "current_question_number": current_question_number,
            "total_questions": total_questions,
            "completed": completed,
            "editing": editing,
            "answered_question_ids": list(responses.keys()),
            "current_question": current_question.model_dump() if current_question is not None else None,
        }

        response = self.client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": str(state_payload)},
            ],
            text_format=LLMUserMessageAnalysis,
        )
        result = response.output_parsed
        print(f"[LLM] intent={result.intent} | confidence={result.confidence} | question_number={result.question_number}")
        print(f"[LLM] extracted_answer={result.extracted_answer!r}")
        print(f"[LLM] note={result.assistant_note!r}")
        return result

    def _question_block(self, question: Question, number: int, total: int) -> str:
        """Deterministic, always-correct question presentation.

        Shows the question and its options ONCE, so an employee can either tap the
        interactive widget or type the answer in the chat — both paths work. Never
        machine-invented format hints (which the LLM used to get wrong, e.g.
        'provide 2 letters'). The options must NOT also be embedded in the prompt.
        """
        lines = [f"**Question {number} of {total}**", "", question.prompt]
        if question.options:
            lines.append("")
            lines.extend(f"- {option}" for option in question.options)
        return "\n".join(lines)

    def compose_question_message(self, *, question: Question, number: int, total: int, greeting: bool = False) -> str:
        # Deterministic (no LLM call) so each question appears instantly. The LLM
        # is reserved for understanding the employee's answer, not for wording.
        block = self._question_block(question, number, total)
        if greeting:
            return "Welcome — thanks for taking a few minutes to share your feedback.\n\n" + block
        return block

    def compose_invalid_message(
        self,
        *,
        error: str,
        question: Question,
        user_answer: str,
        normalized_answer: str | None,
    ) -> str:
        # Deterministic: state the error and show the correct format directly.
        format_guide = self._format_guide(question)
        return f"{error}\n\n**How to answer:**\n{format_guide}"

    def compose_accepted_then_next_message(
        self,
        *,
        next_question: Question,
        number: int,
        total: int,
        user_message: str,
        validated_answer: Any,
    ) -> str:
        # Deterministic acknowledgment + next question — no LLM call, so moving
        # between questions is instant (the only per-answer LLM call is the one
        # that understands the answer).
        block = self._question_block(next_question, number, total)
        return "Thanks, that's saved.\n\n" + block

    def compose_edit_start_message(
        self,
        *,
        question: Question,
        number: int,
        total: int,
        previous_answer: str,
    ) -> str:
        return (
            f"Sure — going back to Question {number}.\n\n"
            f"Previous answer: `{previous_answer}`\n\n"
            f"{self._question_block(question, number, total)}\n\n"
            "Send your updated answer below."
        )

    def compose_edit_saved_message(
        self,
        *,
        return_question: Question | None,
        return_number: int | None,
        total: int,
        completed: bool,
    ) -> str:
        if completed or return_question is None or return_number is None:
            return "Your previous answer was updated.\n\nThe survey is complete — all your responses have been saved."
        return (
            "Your previous answer was updated.\n\nLet's continue where we left off.\n\n"
            + self._question_block(return_question, return_number, total)
        )

    def compose_completed_message(self, *, user_message: str, validated_answer: Any) -> str:
        return (
            "🎉 That's the last one — the survey is complete. All your responses have been saved.\n\n"
            "If you want to change an answer, type: `go back to question 1`."
        )

    def compose_help_message(self, *, question: Question | None, number: int | None, total: int) -> str:
        if question is None or number is None:
            return "You can revisit a previous answer by typing: `go back to question 1`."
        return (
            "No problem — here's the current question again:\n\n"
            f"{self._question_block(question, number, total)}\n\n"
            f"**How to answer:**\n{self._format_guide(question)}"
        )

    def compose_progress_message(self, *, answered: int, total: int, completed: bool) -> str:
        status = "complete" if completed else "in progress"
        return f"You've answered {answered}/{total} questions. Status: {status}."

    def compose_unknown_message(self, *, question: Question | None, number: int | None, total: int) -> str:
        if question is None or number is None:
            return "I didn't quite catch that. You can type `go back to question 1`, `show progress`, or answer the current question."
        return (
            "I didn't quite catch that — here's the current question again:\n\n"
            + self._question_block(question, number, total)
        )

    def _format_guide(self, question: Question) -> str:
        """Returns a clear, type-specific format instruction to embed in every message."""
        qt = question.question_type
        opts = question.options

        if qt == "rating":
            lo = int(question.min_value or 1)
            hi = int(question.max_value or 5)
            return (
                f"Reply with a single whole number between {lo} and {hi}.\n"
                f"Example: {hi - 1}"
            )

        if qt == "number":
            parts = []
            if question.min_value is not None:
                parts.append(f"minimum {question.min_value:g}")
            if question.max_value is not None:
                parts.append(f"maximum {question.max_value:g}")
            constraint = f" ({', '.join(parts)})" if parts else ""
            return (
                f"Reply with a plain number{constraint}.\n"
                f"Example: {question.expected_format or '10'}"
            )

        if qt == "percentage":
            return (
                f"Reply with a number between 0 and 100 followed by %.\n"
                f"Example: {question.expected_format or '70%'}"
            )

        if qt == "single_selection":
            listed = "\n".join(f"  - {o}" for o in opts) if opts else "  (see options above)"
            return (
                f"Reply with exactly one of the options below:\n{listed}\n"
                f"You can type the full label or just the letter code if one is shown.\n"
                f"Example: {question.expected_format or (opts[0] if opts else 'one option')}"
            )

        if qt == "multiple_selection":
            max_c = f"up to {question.max_choices}" if question.max_choices else "one or more"
            listed = "\n".join(f"  - {o}" for o in opts) if opts else "  (see options above)"
            return (
                f"Reply with {max_c} of the options below, separated by commas:\n{listed}\n"
                f"Example: {question.expected_format or 'Option A, Option B'}"
            )

        if qt == "distribution":
            listed = "\n".join(f"  - {o}" for o in opts) if opts else "  (see options above)"
            example = ", ".join(
                f"{round(100 // len(opts) if opts else 50)}% {o}" for o in opts[:3]
            ) if opts else "40% deep work, 35% meetings, 25% admin"
            return (
                f"Assign a percentage to each category — they must add up to exactly 100%.\n"
                f"Categories:\n{listed}\n"
                f"Format: [percentage]% [category], [percentage]% [category], ...\n"
                f"Example: {example}"
            )

        if qt == "hours_distribution":
            return (
                f"Reply with: your total hours per week, then 3 percentages for individual work, "
                f"collaborative work, and other. The 3 percentages must add up to exactly 100%.\n"
                f"Format: [hours], [individual]%, [collaborative]%, [other]%\n"
                f"Example: {question.expected_format or '40, 50%, 30%, 20%'}"
            )

        if qt == "free_text":
            return (
                f"Reply with a text answer (at least {question.min_length} characters).\n"
                f"Example: {question.expected_format or 'Your answer here'}"
            )

        return f"Expected format: {question.expected_format}"

    @property
    def client(self) -> Any:
        if self._client is not None:
            return self._client

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is missing. Add it to your environment or set OPENAI_FAKE_MODE=true for local tests."
            )

        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        return self._client

    def _fake_analyze_user_message(
        self,
        *,
        user_message: str,
        current_question: Question | None,
        current_question_number: int | None,
    ) -> LLMUserMessageAnalysis:
        text = user_message.strip().lower()

        if text in {"help", "what format", "format", "how do i answer"} or "expected format" in text:
            return LLMUserMessageAnalysis(intent="help", assistant_note="User asked for help.")

        if "progress" in text or "how many" in text or "left" in text:
            return LLMUserMessageAnalysis(intent="show_progress", assistant_note="User asked for progress.")

        if "cancel" in text and "edit" in text:
            return LLMUserMessageAnalysis(intent="cancel_edit", assistant_note="User wants to cancel editing.")

        number_match = re.search(r"(?:go\s+back\s+to|back\s+to|edit|change|update|redo)\s+(?:question\s*)?(?:q\s*)?(\d{1,2})", text)
        if number_match:
            return LLMUserMessageAnalysis(
                intent="go_to_question",
                question_number=int(number_match.group(1)),
                assistant_note="User wants to edit a specific question.",
            )

        if text in {"back", "go back", "previous", "previous question", "go to previous question"}:
            return LLMUserMessageAnalysis(intent="previous_question", assistant_note="User wants previous question.")

        extracted = self._fake_extract_answer(user_message, current_question)
        return LLMUserMessageAnalysis(
            intent="answer_current_question",
            extracted_answer=extracted,
            assistant_note=f"Treating as answer to question {current_question_number}.",
        )

    def _fake_extract_answer(self, answer: str, question: Question | None) -> ExtractedAnswer | None:
        if question is None:
            return None

        cleaned = answer.strip()
        qt = question.question_type

        if qt == "rating":
            m = re.search(r"\d+", cleaned)
            return ExtractedAnswer(rating=int(m.group(0))) if m else None

        if qt == "number":
            value_text = cleaned.lower()
            for unit in ("minutes", "minute", "mins", "min"):
                value_text = value_text.replace(unit, "")
            m = re.search(r"\d+(?:\.\d+)?", value_text.strip())
            return ExtractedAnswer(number=float(m.group(0))) if m else None

        if qt == "percentage":
            m = re.search(r"\d+(?:\.\d+)?", cleaned.replace("%", ""))
            return ExtractedAnswer(percentage=float(m.group(0))) if m else None

        if qt == "distribution":
            parts = [p.strip() for p in cleaned.split(",") if p.strip()]
            entries = []
            for part in parts:
                m = re.match(r"^(\d+(?:\.\d+)?)\s*%\s+(.+)$", part)
                if not m:
                    return None
                entries.append(LabeledDistributionEntry(label=m.group(2).strip(), percentage=float(m.group(1))))
            return ExtractedAnswer(labeled_distribution=entries) if entries else None

        if qt == "hours_distribution":
            numbers = [float(v) for v in re.findall(r"\d+(?:\.\d+)?", cleaned)]
            if len(numbers) < 4:
                return None
            return ExtractedAnswer(
                hours_distribution=HoursDistributionData(
                    hours_per_week=numbers[0],
                    individual_work_pct=numbers[1],
                    collaborative_work_pct=numbers[2],
                    other_pct=numbers[3],
                )
            )

        if qt == "single_selection":
            return ExtractedAnswer(single_selection=cleaned)

        if qt == "multiple_selection":
            if "," in cleaned or ";" in cleaned:
                options = [p.strip() for p in re.split(r"[,;]+", cleaned) if p.strip()]
            else:
                words = cleaned.split()
                options = words if all(len(w) == 1 and w.isalpha() for w in words) else [cleaned]
            return ExtractedAnswer(multiple_selection=options)

        if qt == "free_text":
            return ExtractedAnswer(free_text=cleaned) if cleaned else None

        return None

    def _env_flag(self, name: str) -> bool:
        return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}
