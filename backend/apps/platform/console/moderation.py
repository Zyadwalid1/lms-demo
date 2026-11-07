"""Console > Reviews: moderation of reviews, questions and answers, and reported content."""

from datetime import datetime
from uuid import UUID

from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Schema

from apps.engagement import services as social
from apps.engagement.models import Answer, Question, Review

from ..services import audit_request
from .common import ConsoleOkOut, clamp, router, staff


class ConsoleHideIn(Schema):
    hide: bool


class ConsoleReviewModOut(Schema):
    id: UUID
    course: str
    author: str
    rating: int
    body: str
    status: str
    created_at: datetime


@router.get("/moderation/reviews", response=list[ConsoleReviewModOut])
def reviews(request, max_rating: int = 5, limit: int = 100):
    staff(request)
    rows = (
        Review.objects.filter(rating__lte=max_rating).select_related("user", "course").order_by("-created_at")
    )
    return [{"id": r.id, "course": r.course.title, "author": r.user.full_name, "rating": r.rating, "body": r.body,
             "status": r.status, "created_at": r.created_at} for r in rows[: clamp(limit, 500)]]  # fmt: skip


@router.post("/moderation/reviews/{review_id}", response=ConsoleOkOut)
def moderate_review(request, review_id: str, body: ConsoleHideIn):
    staff(request)
    social.moderate_review(review=get_object_or_404(Review, pk=review_id), hide=body.hide)
    audit_request(request, "review.moderate", "review", review_id, {"hide": body.hide})
    return {"ok": True}


@router.post("/moderation/questions/{question_id}", response=ConsoleOkOut)
def moderate_question(request, question_id: str, body: ConsoleHideIn):
    staff(request)
    Question.objects.filter(pk=question_id).update(hidden_at=timezone.now() if body.hide else None)
    audit_request(request, "question.moderate", "question", question_id, {"hide": body.hide})
    return {"ok": True}


@router.post("/moderation/answers/{answer_id}", response=ConsoleOkOut)
def moderate_answer(request, answer_id: str, body: ConsoleHideIn):
    staff(request)
    a = get_object_or_404(Answer, pk=answer_id)
    Answer.objects.filter(pk=a.pk).update(
        hidden_at=timezone.now() if body.hide else None
    )  # counters: trigger
    audit_request(request, "answer.moderate", "answer", answer_id, {"hide": body.hide})
    return {"ok": True}
