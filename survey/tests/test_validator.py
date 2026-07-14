"""Unit tests for the deterministic answer validator.

Self-contained: questions are built inline so the suite needs no database,
no OpenAI key, and no default question bank.
"""

from backend.models import ExtractedAnswer, LabeledDistributionEntry, Question
from backend.services.validator import AnswerValidator

V = AnswerValidator()


def q(**overrides) -> Question:
    base = dict(id="q", category="General", question_type="free_text", prompt="?", options=[])
    base.update(overrides)
    return Question(**base)


def test_rating_within_range():
    result = V.validate("4", q(question_type="rating", min_value=1, max_value=5))
    assert result.valid is True
    assert result.normalized_answer == 4


def test_rating_rejects_text():
    result = V.validate("very good", q(question_type="rating", min_value=1, max_value=5))
    assert result.valid is False


def test_rating_out_of_range():
    result = V.validate("9", q(question_type="rating", min_value=1, max_value=5))
    assert result.valid is False


def test_number_accepts_units():
    result = V.validate("25 minutes", q(question_type="number", min_value=0, max_value=100))
    assert result.valid is True
    assert result.normalized_answer == 25


def test_percentage_without_symbol():
    result = V.validate("70", q(question_type="percentage"))
    assert result.valid is True
    assert result.normalized_answer == {"value": 70, "unit": "%"}


def test_single_selection_matches_label():
    result = V.validate("Full-time", q(question_type="single_selection", options=["Full-time", "Part-time"]))
    assert result.valid is True
    assert result.normalized_answer == "Full-time"


def test_multiple_selection():
    result = V.validate("Office, Home", q(question_type="multiple_selection", options=["Office", "Home", "Cafe"]))
    assert result.valid is True
    assert result.normalized_answer == ["Office", "Home"]


def test_free_text_min_length():
    result = V.validate("Senior Financial Analyst", q(question_type="free_text", min_length=2))
    assert result.valid is True


def test_distribution_valid():
    result = V.validate("30% work, 70% meetings", q(question_type="distribution", options=["work", "meetings"]))
    assert result.valid is True
    assert result.normalized_answer == [
        {"label": "work", "percentage": 30},
        {"label": "meetings", "percentage": 70},
    ]


def test_distribution_must_total_100():
    result = V.validate("30% work, 40% meetings", q(question_type="distribution", options=["work", "meetings"]))
    assert result.valid is False
    assert "100" in (result.error or "")


def test_distribution_structured_from_extracted_answer():
    extracted = ExtractedAnswer(
        labeled_distribution=[
            LabeledDistributionEntry(label="work", percentage=60),
            LabeledDistributionEntry(label="meetings", percentage=40),
        ]
    )
    result = V.validate_structured(extracted, q(question_type="distribution", options=["work", "meetings"]))
    assert result.valid is True
    assert result.normalized_answer == [
        {"label": "work", "percentage": 60},
        {"label": "meetings", "percentage": 40},
    ]
