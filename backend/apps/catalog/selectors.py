"""Optimised catalog READS. All run under RLS (private content stays in its company)."""

import random

from django.db.models import Prefetch

from .models import CourseVersion, Lecture, Quiz, QuizQuestion, Section


def curriculum(version: CourseVersion):
    """Sections with their lectures, in order, in two queries."""
    lectures = Lecture.objects.order_by("position").select_related("video")
    return version.sections.order_by("position").prefetch_related(Prefetch("lectures", queryset=lectures))


def learner_quiz(quiz: Quiz, *, seed: int | None = None) -> dict:
    """The quiz as a learner may see it: NO correct flags, NO matching pairs.
    Grading is done on the server against the stored options."""
    rng = random.Random(seed)  # noqa: S311 - shuffling for display, not security
    questions = list(quiz.questions.order_by("position").prefetch_related("options"))
    if quiz.shuffle_questions:
        rng.shuffle(questions)
    out = []
    for q in questions:
        opts = sorted(q.options.all(), key=lambda o: o.position)
        item = {"id": str(q.id), "kind": q.kind, "prompt": q.prompt, "points": q.points}
        if q.kind == QuizQuestion.Kind.MATCHING:
            right = [o.match_text for o in opts]
            rng.shuffle(right)  # sides shown separately, never paired
            item["left"] = [{"id": str(o.id), "body": o.body} for o in opts]
            item["right"] = right
        elif q.kind in (
            QuizQuestion.Kind.FILL_BLANK,
            QuizQuestion.Kind.SHORT_ANSWER,
            QuizQuestion.Kind.ESSAY,
        ):
            item["blanks"] = q.prompt.count("___") if q.kind == QuizQuestion.Kind.FILL_BLANK else 0
        else:
            if quiz.shuffle_options and q.kind != QuizQuestion.Kind.TRUE_FALSE:
                rng.shuffle(opts)
            item["options"] = [{"id": str(o.id), "body": o.body} for o in opts]
        out.append(item)
    return {"id": str(quiz.id), "time_limit_sec": quiz.time_limit_sec, "questions": out}


__all__ = ["curriculum", "learner_quiz", "Section"]
