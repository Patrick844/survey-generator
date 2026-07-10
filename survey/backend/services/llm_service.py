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


class LLMReply(BaseModel):
    """Structured output returned by OpenAI when composing chatbot copy."""

    assistant_message: str


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
- distribution (coded, options A B C...)
                  → extracted_answer.coded_distribution = dict mapping each code to its percentage.
                    Include ONLY codes the user explicitly mentioned.
                    If the user gave bare numbers with NO letter codes, set coded_distribution = null.
- distribution (labeled, free-form labels)
                  → extracted_answer.labeled_distribution = list of {label, percentage} objects.
                    Use ONLY labels the user explicitly wrote. Do NOT invent labels.
                    If the user did not provide labels (e.g. typed only "10" or "50%"), set labeled_distribution = null.
- hours_distribution
                  → extracted_answer.hours_distribution = {hours_per_week, individual_work_pct, collaborative_work_pct, other_pct}.
                    All four fields must come from the user's message. If any are missing, set hours_distribution = null.
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

    def compose_question_message(self, *, question: Question, number: int, total: int, greeting: bool = False) -> str:
        if self.fake_mode:
            prefix = "Hey, let's get started.\n\n" if greeting else ""
            return prefix + self._template_question_message(question=question, number=number, total=total)

        format_guide = self._format_guide(question)
        prompt = f"""
Write the next chatbot message for an employee workplace survey.

Requirements:
- Warm, human, conversational tone — not stiff or robotic.
- If greeting=true, open with a short welcoming sentence (do NOT use "Hey, let's get started" verbatim).
- Show the question number: Question {number} of {total}.
- Include the question text exactly as written.
- Include the options exactly when provided (list them clearly).
- Include the format guide below word-for-word in a clearly labelled "How to answer:" section.
- Keep it concise — no filler phrases like "Great!" or "Wonderful!".

Format guide to include:
{format_guide}

Data:
greeting={greeting}
question={question.model_dump()}
""".strip()
        return self._compose_reply(prompt)

    def compose_invalid_message(
        self,
        *,
        error: str,
        question: Question,
        user_answer: str,
        normalized_answer: str | None,
    ) -> str:
        if self.fake_mode:
            return (
                f"That response is not in the expected format. {error}\n\n"
                f"Please resend your response based on this format: {question.expected_format}"
            )

        format_guide = self._format_guide(question)
        prompt = f"""
Write a short chatbot message telling the employee their response is invalid.

Requirements:
- Be polite and direct — do not be vague.
- State exactly what went wrong using the validation error below.
- Show the correct format using the format guide below word-for-word.
- Show a concrete example of a valid answer.
- Do not ask a new question.

Validation error: {error}
Employee typed: {user_answer}
Format guide: {format_guide}
Question type: {question.question_type}
Options (if any): {question.options}
""".strip()
        return self._compose_reply(prompt)

    def compose_accepted_then_next_message(
        self,
        *,
        next_question: Question,
        number: int,
        total: int,
        user_message: str,
        validated_answer: Any,
    ) -> str:
        if self.fake_mode:
            return "Good, your answer was saved.\n\n" + self._template_question_message(
                question=next_question,
                number=number,
                total=total,
            )

        prompt = f"""
Write a chatbot message after a valid survey answer.

Requirements:
- Briefly acknowledge the employee's specific answer (user_message and validated_answer below) in a natural, warm way — one short sentence. Do not just say "Good, your answer was saved." Reference what they actually said.
- Then ask the next question.
- Include: Question {number}/{total}
- Include the question text exactly.
- Include the expected format exactly.
- Include options exactly when provided.

Employee's raw answer: {user_message}
Validated answer (normalized): {validated_answer}
Next question data: {next_question.model_dump()}
""".strip()
        return self._compose_reply(prompt)

    def compose_edit_start_message(
        self,
        *,
        question: Question,
        number: int,
        total: int,
        previous_answer: str,
    ) -> str:
        if self.fake_mode:
            return (
                f"Sure — going back to Question {number}.\n\n"
                f"Previous answer: `{previous_answer}`\n\n"
                f"{self._template_question_message(question=question, number=number, total=total)}\n\n"
                "Please send your updated answer."
            )

        prompt = f"""
Write a chatbot message for editing a previous survey answer.

Requirements:
- Say we are going back to Question {number}.
- Show previous answer exactly: {previous_answer}
- Ask the same question again.
- Include expected format exactly.
- Include options exactly when provided.
- End by asking the employee to send the updated answer.

Question data:
{question.model_dump()}
Total questions: {total}
""".strip()
        return self._compose_reply(prompt)

    def compose_edit_saved_message(
        self,
        *,
        return_question: Question | None,
        return_number: int | None,
        total: int,
        completed: bool,
    ) -> str:
        if self.fake_mode:
            if completed or return_question is None or return_number is None:
                return "Good, your previous answer was updated.\n\nGreat, the survey is complete. All your responses have been saved."
            return (
                "Good, your previous answer was updated.\n\n"
                "Let's continue where we left off.\n\n"
                + self._template_question_message(question=return_question, number=return_number, total=total)
            )

        prompt = f"""
Write a chatbot message after the employee updated a previous answer.

Requirements:
- Start with: Good, your previous answer was updated.
- If completed=true, tell them the survey is complete and responses are saved.
- If completed=false, say: Let's continue where we left off.
- If there is a return question, ask it next with question number, expected format, and options exactly.

completed={completed}
return_number={return_number}
total={total}
return_question={return_question.model_dump() if return_question is not None else None}
""".strip()
        return self._compose_reply(prompt)

    def compose_completed_message(self, *, user_message: str, validated_answer: Any) -> str:
        if self.fake_mode:
            return (
                "Great, the survey is complete. All your responses have been saved.\n\n"
                "If you want to edit a previous answer, say something like: `go back to question 1`."
            )

        prompt = f"""
Write a short friendly survey completion message.

Requirements:
- Briefly acknowledge the employee's final answer (user_message and validated_answer below) naturally — one short sentence.
- Then say the survey is complete and all responses have been saved.
- End by telling them they can still edit any answer by saying: go back to question 1.

Employee's final raw answer: {user_message}
Validated final answer (normalized): {validated_answer}
""".strip()
        return self._compose_reply(prompt)

    def compose_help_message(self, *, question: Question | None, number: int | None, total: int) -> str:
        if self.fake_mode:
            if question is None or number is None:
                return "You can edit a previous answer by saying: go back to question 1."
            return (
                "No problem — answer the current question using this format:\n\n"
                f"{question.expected_format}\n\n"
                + self._template_question_message(question=question, number=number, total=total)
            )

        prompt = f"""
Write a helpful chatbot message explaining how to answer or navigate.

Requirements:
- Mention they can type things like: go back to question 1.
- If a current question exists, explain the expected format exactly and repeat the current question.

Current number: {number}
Total questions: {total}
Question: {question.model_dump() if question is not None else None}
""".strip()
        return self._compose_reply(prompt)

    def compose_progress_message(self, *, answered: int, total: int, completed: bool) -> str:
        if self.fake_mode:
            status = "complete" if completed else "in progress"
            return f"You have answered {answered}/{total} questions. Current status: {status}."

        prompt = f"Write a concise survey progress message. answered={answered}, total={total}, completed={completed}."
        return self._compose_reply(prompt)

    def compose_unknown_message(self, *, question: Question | None, number: int | None, total: int) -> str:
        if self.fake_mode:
            if question is None or number is None:
                return "I didn't fully understand. You can say: go back to question 1, show progress, or start again."
            return (
                "I didn't fully understand. Please answer the current question using the expected format.\n\n"
                + self._template_question_message(question=question, number=number, total=total)
            )

        prompt = f"""
Write a short chatbot recovery message because the user's message was unclear.

Requirements:
- Be friendly.
- Ask them to answer the current question using the expected format.
- Mention they can type: go back to question 1.
- If a current question exists, repeat it.

Current number: {number}
Total questions: {total}
Question: {question.model_dump() if question is not None else None}
""".strip()
        return self._compose_reply(prompt)

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
            if question.distribution_mode == "coded":
                listed = "\n".join(f"  - {o}" for o in opts) if opts else "  (see options above)"
                example = question.expected_format or (
                    ", ".join(f"{o} {round(100 // len(opts) if opts else 50)}%" for o in opts[:3]) if opts else "A 40%, B 35%, C 25%"
                )
                return (
                    f"Assign a percentage to each option — they must add up to exactly 100%.\n"
                    f"Options:\n{listed}\n"
                    f"Format: [letter] [percentage]%, [letter] [percentage]%, ...\n"
                    f"Example: {example}"
                )
            else:
                return (
                    f"List each category with its percentage — they must add up to exactly 100%.\n"
                    f"Format: [percentage]% [label], [percentage]% [label], ...\n"
                    f"Example: {question.expected_format or '40% deep work, 35% meetings, 25% admin'}"
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

    def _compose_reply(self, prompt: str) -> str:
        response = self.client.responses.parse(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": "You write concise, warm chatbot messages for an employee survey app. Use markdown: blank lines between paragraphs, bullet lists where useful. Never use 'Great!', 'Wonderful!' or similar filler openers.",
                },
                {"role": "user", "content": prompt},
            ],
            text_format=LLMReply,
        )
        return response.output_parsed.assistant_message

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
            if question.distribution_mode == "coded":
                pattern = re.compile(r"\b([A-Za-z])\b\s*[:=-]?\s*(\d+(?:\.\d+)?)\s*%?")
                matches = pattern.findall(cleaned)
                if not matches:
                    return None
                return ExtractedAnswer(coded_distribution={code.upper(): float(val) for code, val in matches})
            else:
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

    def _template_question_message(self, *, question: Question, number: int, total: int) -> str:
        message = [
            f"Question {number}/{total}",
            question.prompt,
            f"Expected format: {question.expected_format}",
        ]
        if question.options:
            options = "\n".join(f"- {option}" for option in question.options)
            message.append(f"Options:\n{options}")
        return "\n\n".join(message)

    def _env_flag(self, name: str) -> bool:
        return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}
