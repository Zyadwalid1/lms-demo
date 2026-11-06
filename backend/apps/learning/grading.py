"""Server-side quiz grading. Answers never leave the server (catalog.selectors.learner_quiz);
the browser sends responses, this module scores them against the stored options.

Response formats per question kind:
    single_choice / true_false   "<option id>"
    multiple_choice              ["<option id>", ...]          all-or-nothing
    matching                     {"<left option id>": "<right text>"}   partial credit
    fill_blank                   ["answer for blank 0", "blank 1", ...]  partial credit
    short_answer                 "text"
    essay                        "text"                         graded by the instructor
"""

import re
from decimal import ROUND_HALF_UP, Decimal

from apps.catalog.models import QuizQuestion

Kind = QuizQuestion.Kind
TWO_PLACES = Decimal("0.01")


def _norm(text, case_sensitive: bool) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text if case_sensitive else text.casefold()


def _q(value) -> Decimal:
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def grade_question(question: QuizQuestion, response) -> tuple[Decimal | None, bool]:
    """Return (points, needs_manual). points is None when an instructor must grade it."""
    options = list(question.options.all())
    points = Decimal(question.points)

    if question.kind == Kind.ESSAY:
        return None, True

    if question.kind in (Kind.SINGLE_CHOICE, Kind.TRUE_FALSE):
        correct = {str(o.id) for o in options if o.is_correct}
        return (points if str(response or "") in correct else Decimal(0)), False

    if question.kind == Kind.MULTIPLE_CHOICE:
        correct = {str(o.id) for o in options if o.is_correct}
        chosen = {str(x) for x in (response or [])} if isinstance(response, list) else set()
        return (points if chosen == correct else Decimal(0)), False

    if question.kind == Kind.MATCHING:
        if not options:
            return Decimal(0), False
        given = response if isinstance(response, dict) else {}
        right = sum(
            1
            for o in options
            if _norm(given.get(str(o.id)), question.case_sensitive)
            == _norm(o.match_text, question.case_sensitive)
        )
        return _q(points * right / len(options)), False

    if question.kind == Kind.FILL_BLANK:
        accepted: dict[int, set[str]] = {}
        for o in options:
            if o.is_correct:
                accepted.setdefault(o.blank_index, set()).add(_norm(o.body, question.case_sensitive))
        if not accepted:
            return Decimal(0), False
        given = response if isinstance(response, list) else [response]
        right = sum(
            1
            for idx, answers in accepted.items()
            if idx < len(given) and _norm(given[idx], question.case_sensitive) in answers
        )
        return _q(points * right / len(accepted)), False

    if question.kind == Kind.SHORT_ANSWER:
        accepted = {_norm(o.body, question.case_sensitive) for o in options if o.is_correct}
        return (points if _norm(response, question.case_sensitive) in accepted else Decimal(0)), False

    return Decimal(0), False
