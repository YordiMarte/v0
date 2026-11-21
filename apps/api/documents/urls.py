from django.urls import path

from documents.views import DocumentViewSet

urlpatterns = [
    path(
        "organizations/<uuid:org_id>/documents/",
        DocumentViewSet.as_view({"get": "list", "post": "create"}),
        name="document-list",
    ),
    path(
        "organizations/<uuid:org_id>/documents/<uuid:pk>/",
        DocumentViewSet.as_view({"get": "retrieve", "delete": "destroy"}),
        name="document-detail",
    ),
    path(
        "organizations/<uuid:org_id>/documents/<uuid:pk>/download/",
        DocumentViewSet.as_view({"get": "download"}),
        name="document-download",
    ),
    path(
        "organizations/<uuid:org_id>/documents/<uuid:pk>/reprocess/",
        DocumentViewSet.as_view({"post": "reprocess"}),
        name="document-reprocess",
    ),
]
