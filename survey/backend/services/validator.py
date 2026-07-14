from __future__ import annotations

import re
from difflib import get_close_matches
from typing import Any

from backend.models import ExtractedAnswer, Question, ValidationResult


class AnswerValidator:
    """Format-aware validation and normalization for survey answers."""

    def validate(self, answer: str, question: Question) -> ValidationResult:
        cleaned = answer.strip()

        print(f"[VALIDATOR] id={question.id} type={question.question_type}")
        print(f"[VALIDATOR] Input: {cleaned!r}")

        if not cleaned:
            result = ValidationResult(valid=False, error="Please send an answer before continuing.")
            print(f"[VALIDATOR] Result: INVALID (empty)")
            return result

        validators = {
            "rating": self._validate_rating,
            "distribution": self._validate_distribution,
            "hours_distribution": self._validate_hours_distribution,
            "single_selection": self._validate_single_selection,
            "multiple_selection": self._validate_multiple_selection,
            "number": self._validate_number,
            "percentage": self._validate_percentage,
            "free_text": self._validate_free_text,
        }

        validator = validators.get(question.question_type)
        if validator is None:
            result = ValidationResult(valid=False, error=f"Unsupported question type: {question.question_type}")
            print(f"[VALIDATOR] Result: INVALID (unsupported type)")
            return result

        result = validator(cleaned, question)
        print(f"[VALIDATOR] Result: {'VALID' if result.valid else 'INVALID'} | error={result.error!r} | stored={result.normalized_answer!r}")
        return result

    def validate_structured(self, extracted: ExtractedAnswer, question: Question) -> ValidationResult:
        print(f"[VALIDATOR] id={question.id} type={question.question_type}")
        print(f"[VALIDATOR] Extracted: {extracted.model_dump()!r}")

        qt = question.question_type

        if qt == "rating":
            if extracted.rating is None:
                result = ValidationResult(valid=False, error="I couldn't read your rating. Please send a whole number, for example: 4.")
            else:
                result = self._validate_range(extracted.rating, question, "Rating")

        elif qt == "number":
            if extracted.number is None:
                result = ValidationResult(valid=False, error="I couldn't read your number. Please send a plain number.")
            else:
                value = self._clean_number(extracted.number)
                result = self._validate_range(value, question, "Number")
                if result.valid:
                    result.normalized_answer = value

        elif qt == "percentage":
            if extracted.percentage is None:
                result = ValidationResult(valid=False, error="I couldn't read your percentage. Please send a number, for example: 70%.")
            else:
                value = self._clean_number(extracted.percentage)
                range_result = self._validate_range(value, question, "Percentage")
                result = ValidationResult(valid=True, normalized_answer={"value": value, "unit": "%"}) if range_result.valid else range_result

        elif qt == "distribution":
            if extracted.labeled_distribution is None:
                result = ValidationResult(valid=False, error="Please assign a percentage to each category so they add up to 100%.")
            else:
                result = self._validate_labeled_distribution_structured(extracted.labeled_distribution)

        elif qt == "hours_distribution":
            if extracted.hours_distribution is None:
                result = ValidationResult(valid=False, error="Please send hours plus 3 percentages, for example: 40, 40, 40, 20.")
            else:
                result = self._validate_hours_distribution_structured(extracted.hours_distribution, question)

        elif qt == "single_selection":
            if extracted.single_selection is None:
                result = ValidationResult(valid=False, error="Please choose one of the available options.")
            else:
                result = self._validate_single_selection(extracted.single_selection, question)

        elif qt == "multiple_selection":
            if not extracted.multiple_selection:
                result = ValidationResult(valid=False, error="Please select at least one option.")
            else:
                result = self._validate_multiple_selection_structured(extracted.multiple_selection, question)

        elif qt == "free_text":
            if extracted.free_text is None:
                result = ValidationResult(valid=False, error="Please send a text answer.")
            else:
                result = self._validate_free_text(extracted.free_text, question)

        else:
            result = ValidationResult(valid=False, error=f"Unsupported question type: {qt}")

        print(f"[VALIDATOR] Result: {'VALID' if result.valid else 'INVALID'} | error={result.error!r} | stored={result.normalized_answer!r}")
        return result

    def _validate_labeled_distribution_structured(self, entries: list) -> ValidationResult:
        if not entries:
            return ValidationResult(valid=False, error="Please send at least one percentage with a label.")

        normalized = [{"label": e.label, "percentage": self._clean_number(e.percentage)} for e in entries]
        total = round(sum(float(e.percentage) for e in entries), 2)
        if total != 100:
            return ValidationResult(valid=False, error=f"Percentages must add up to 100%. Current total is {total:g}%.")

        return ValidationResult(valid=True, normalized_answer=normalized)

    def _validate_hours_distribution_structured(self, data: Any, question: Question) -> ValidationResult:
        hours = data.hours_per_week

        if question.min_value is not None and hours < question.min_value:
            return ValidationResult(valid=False, error=f"Hours must be at least {question.min_value:g}.")
        if question.max_value is not None and hours > question.max_value:
            return ValidationResult(valid=False, error=f"Hours must be at most {question.max_value:g}.")

        total = round(data.individual_work_pct + data.collaborative_work_pct + data.other_pct, 2)
        if total != 100:
            return ValidationResult(valid=False, error=f"The 3 percentages must add up to 100%. Current total is {total:g}%.")

        return ValidationResult(valid=True, normalized_answer={
            "hours_per_week": self._clean_number(hours),
            "individual_work_percentage": self._clean_number(data.individual_work_pct),
            "collaborative_work_percentage": self._clean_number(data.collaborative_work_pct),
            "other_percentage": self._clean_number(data.other_pct),
        })

    def _validate_multiple_selection_structured(self, options: list[str], question: Question) -> ValidationResult:
        selected: list[str] = []
        for option in options:
            matched = self._match_option(option, question.options)
            if matched is None:
                return ValidationResult(valid=False, error=f"'{option}' is not one of the available options.")
            if matched not in selected:
                selected.append(matched)

        if question.max_choices is not None and len(selected) > question.max_choices:
            return ValidationResult(valid=False, error=f"Please select up to {question.max_choices} option(s).")

        return ValidationResult(valid=True, normalized_answer=selected)

    def _validate_rating(self, answer: str, question: Question) -> ValidationResult:
        try:
            value = int(answer)
        except ValueError:
            return ValidationResult(valid=False, error="Please send a whole number rating.")

        return self._validate_range(value, question, "Rating")

    def _validate_number(self, answer: str, question: Question) -> ValidationResult:
        value_text = answer.lower().replace("minutes", "").replace("minute", "").replace("mins", "").replace("min", "").strip()
        try:
            value = float(value_text)
        except ValueError:
            return ValidationResult(valid=False, error="Please send a valid number.")

        if value.is_integer():
            value = int(value)

        return self._validate_range(value, question, "Number")

    def _validate_percentage(self, answer: str, question: Question) -> ValidationResult:
        value_text = answer.replace("%", "").strip()
        try:
            value = float(value_text)
        except ValueError:
            return ValidationResult(valid=False, error="Please send a valid percentage, for example: 30%.")

        if value.is_integer():
            value = int(value)

        result = self._validate_range(value, question, "Percentage")
        if result.valid:
            result.normalized_answer = {"value": value, "unit": "%"}
        return result

    def _validate_range(self, value: float, question: Question, label: str) -> ValidationResult:
        min_value = question.min_value
        max_value = question.max_value

        if min_value is not None and value < min_value:
            return ValidationResult(valid=False, error=f"{label} must be at least {min_value:g}.")

        if max_value is not None and value > max_value:
            return ValidationResult(valid=False, error=f"{label} must be at most {max_value:g}.")

        return ValidationResult(valid=True, normalized_answer=value)

    def _validate_free_text(self, answer: str, question: Question) -> ValidationResult:
        if len(answer) < question.min_length:
            return ValidationResult(valid=False, error="Please send a more complete answer.")

        return ValidationResult(valid=True, normalized_answer=answer)

    def _validate_single_selection(self, answer: str, question: Question) -> ValidationResult:
        selected = self._match_option(answer, question.options)

        if selected is None:
            return ValidationResult(
                valid=False,
                error="Please choose one of the available options.",
            )

        return ValidationResult(valid=True, normalized_answer=selected)

    def _validate_multiple_selection(self, answer: str, question: Question) -> ValidationResult:
        tokens = self._split_multi_answer(answer)

        if not tokens:
            return ValidationResult(valid=False, error="Please select at least one option.")

        selected: list[str] = []
        for token in tokens:
            matched = self._match_option(token, question.options)
            if matched is None:
                return ValidationResult(valid=False, error=f"'{token}' is not one of the available options.")
            if matched not in selected:
                selected.append(matched)

        if question.max_choices is not None and len(selected) > question.max_choices:
            return ValidationResult(valid=False, error=f"Please select up to {question.max_choices} option(s).")

        return ValidationResult(valid=True, normalized_answer=selected)

    def _validate_distribution(self, answer: str, question: Question) -> ValidationResult:
        return self._validate_labeled_distribution(answer)

    def _validate_labeled_distribution(self, answer: str) -> ValidationResult:
        # Accepts: 30% Marketing, 20% Finance - Auditing, 50% external parties
        parts = [part.strip() for part in answer.split(",") if part.strip()]

        if not parts:
            return ValidationResult(valid=False, error="Please send percentages and labels, for example: 30% Marketing, 70% external parties.")

        normalized: list[dict[str, Any]] = []
        for part in parts:
            match = re.match(r"^(\d+(?:\.\d+)?)\s*%\s+(.+)$", part)
            if not match:
                return ValidationResult(
                    valid=False,
                    error="Please use the expected format: 30% Marketing, 20% Finance, 50% external parties.",
                )

            percentage = float(match.group(1))
            label = match.group(2).strip()
            if not label:
                return ValidationResult(valid=False, error="Each percentage must have a label after it.")

            normalized.append({"label": label, "percentage": self._clean_number(percentage)})

        total = round(sum(float(item["percentage"]) for item in normalized), 2)
        if total != 100:
            return ValidationResult(valid=False, error=f"Percentages must add up to 100%. Current total is {total:g}%.")

        return ValidationResult(valid=True, normalized_answer=normalized)

    def _validate_hours_distribution(self, answer: str, question: Question) -> ValidationResult:
        numbers = [float(value) for value in re.findall(r"\d+(?:\.\d+)?", answer)]

        if len(numbers) < 4:
            return ValidationResult(
                valid=False,
                error="Please send hours plus 3 percentages, for example: 40, 40, 40, 20.",
            )

        hours = numbers[0]
        percentages = numbers[1:4]
        total = round(sum(percentages), 2)

        if question.min_value is not None and hours < question.min_value:
            return ValidationResult(valid=False, error=f"Hours must be at least {question.min_value:g}.")

        if question.max_value is not None and hours > question.max_value:
            return ValidationResult(valid=False, error=f"Hours must be at most {question.max_value:g}.")

        if total != 100:
            return ValidationResult(valid=False, error=f"The 3 percentages must add up to 100%. Current total is {total:g}%.")

        return ValidationResult(
            valid=True,
            normalized_answer={
                "hours_per_week": self._clean_number(hours),
                "individual_work_percentage": self._clean_number(percentages[0]),
                "collaborative_work_percentage": self._clean_number(percentages[1]),
                "other_percentage": self._clean_number(percentages[2]),
            },
        )

    def _split_multi_answer(self, answer: str) -> list[str]:
        answer = answer.strip()

        # "A, D, E" / "Office, Home"
        if "," in answer or ";" in answer or "\n" in answer:
            return [part.strip() for part in re.split(r"[,;\n]+", answer) if part.strip()]

        # "A D E"
        words = answer.split()
        if all(len(word) == 1 and word.isalpha() for word in words):
            return words

        return [answer]

    def _match_option(self, answer: str, options: list[str]) -> str | None:
        cleaned_answer = self._normalize_text(answer)
        option_map: dict[str, str] = {}

        for option in options:
            code = self._option_code(option)
            label = self._option_label(option)

            option_map[self._normalize_text(option)] = option
            option_map[self._normalize_text(label)] = option

            if code:
                option_map[self._normalize_text(code)] = option

        if cleaned_answer in option_map:
            return option_map[cleaned_answer]

        close_matches = get_close_matches(cleaned_answer, option_map.keys(), n=1, cutoff=0.82)
        if close_matches:
            return option_map[close_matches[0]]

        return None

    def _option_code(self, option: str) -> str | None:
        match = re.match(r"^([A-Za-z])\.", option.strip())
        if match:
            return match.group(1)
        return None

    def _option_label(self, option: str) -> str:
        return re.sub(r"^[A-Za-z]\.\s*", "", option.strip())

    def _normalize_text(self, text: str) -> str:
        text = text.lower().strip()
        text = text.replace("-", " ")
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _clean_number(self, value: float) -> int | float:
        return int(value) if float(value).is_integer() else value
