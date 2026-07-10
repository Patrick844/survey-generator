from backend.questions import get_questions
from backend.services.validator import AnswerValidator


def question(question_id: str):
    return next(item for item in get_questions() if item.id == question_id)


def test_coded_distribution_valid():
    validator = AnswerValidator()
    result = validator.validate("A 20%, B 20%, C 20%, D 20%, E 10%, F 5%, G 3%, H 2%", question("q01"))
    assert result.valid is True


def test_coded_distribution_invalid_total():
    validator = AnswerValidator()
    result = validator.validate("A 20%, B 20%", question("q01"))
    assert result.valid is False
    assert "100" in (result.error or "")


def test_single_selection_accepts_code():
    validator = AnswerValidator()
    result = validator.validate("D", question("q07"))
    assert result.valid is True
    assert result.normalized_answer == "D. Analyzer"


def test_multiple_selection_accepts_codes():
    validator = AnswerValidator()
    result = validator.validate("A, D, E", question("q12"))
    assert result.valid is True
    assert result.normalized_answer == ["A. Time Saving", "D. Sense of Autonomy", "E. Work-Life Balance"]


def test_rating_invalid_text():
    validator = AnswerValidator()
    result = validator.validate("very good", question("q23"))
    assert result.valid is False


def test_hours_distribution_valid():
    validator = AnswerValidator()
    result = validator.validate("40, 40, 40, 20", question("q03"))
    assert result.valid is True
    assert result.normalized_answer["hours_per_week"] == 40


def test_percentage_valid_without_symbol():
    validator = AnswerValidator()
    result = validator.validate("70", question("q28"))
    assert result.valid is True
    assert result.normalized_answer == {"value": 70, "unit": "%"}
