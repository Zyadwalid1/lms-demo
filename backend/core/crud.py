"""Generic CRUD router for simple lookup tables (categories, topics, job roles...).

Business endpoints are written by hand in each app's api.py; use this only where
there is no business logic.
"""

from uuid import UUID

from django.shortcuts import get_object_or_404
from ninja import Router, Schema
from ninja.pagination import paginate

from core.pagination import KeysetPagination


def crud_router(model, in_schema: type[Schema], out_schema: type[Schema], *, auth=None, tags=None) -> Router:
    router = Router(auth=auth, tags=tags)

    @router.get("/", response=list[out_schema])
    @paginate(KeysetPagination)
    def list_items(request):
        return model.objects.all()

    @router.get("/{item_id}", response=out_schema)
    def get_item(request, item_id: UUID):
        return get_object_or_404(model, id=item_id)

    @router.post("/", response={201: out_schema})
    def create_item(request, payload: in_schema):
        return 201, model.objects.create(**payload.dict())

    @router.patch("/{item_id}", response=out_schema)
    def update_item(request, item_id: UUID, payload: in_schema):
        obj = get_object_or_404(model, id=item_id)
        for field, value in payload.dict(exclude_unset=True).items():
            setattr(obj, field, value)
        obj.save()
        return obj

    @router.delete("/{item_id}", response={204: None})
    def delete_item(request, item_id: UUID):
        get_object_or_404(model, id=item_id).delete()
        return 204, None

    return router
