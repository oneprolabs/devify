from django.urls import path

from chat_analysis.api_views import (
    EventDetailAPIView,
    EventNotesAPIView,
    NoteDetailAPIView,
    NoteEvidenceAPIView,
    SpaceEventListCreateAPIView,
    SpaceEventRelationListCreateAPIView,
    SpaceNoteListCreateAPIView,
)

urlpatterns = [
    path(
        "spaces/<int:space_id>/notes",
        SpaceNoteListCreateAPIView.as_view(),
        name="chat-note-list-create",
    ),
    path(
        "notes/<int:note_id>",
        NoteDetailAPIView.as_view(),
        name="chat-note-detail",
    ),
    path(
        "notes/<int:note_id>/evidence",
        NoteEvidenceAPIView.as_view(),
        name="chat-note-evidence",
    ),
    path(
        "spaces/<int:space_id>/events",
        SpaceEventListCreateAPIView.as_view(),
        name="chat-event-list-create",
    ),
    path(
        "events/<int:event_id>",
        EventDetailAPIView.as_view(),
        name="chat-event-detail",
    ),
    path(
        "events/<int:event_id>/notes",
        EventNotesAPIView.as_view(),
        name="chat-event-notes",
    ),
    path(
        "events/<int:event_id>/notes/<int:note_id>",
        EventNotesAPIView.as_view(),
        name="chat-event-note-detail",
    ),
    path(
        "spaces/<int:space_id>/event-relations",
        SpaceEventRelationListCreateAPIView.as_view(),
        name="chat-event-relation-list-create",
    ),
]
