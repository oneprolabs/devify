from django.contrib import admin

from chat_analysis.models import (
    AnalysisJob,
    Event,
    EventNote,
    EventRelation,
    Note,
    NoteEvidence,
)


@admin.register(AnalysisJob)
class AnalysisJobAdmin(admin.ModelAdmin):
    list_display = (
        "id", "space", "created_by", "request_key", "state", "created_at"
    )
    list_filter = ("state",)
    search_fields = ("request_key", "uuid", "lease_owner")
    readonly_fields = [field.name for field in AnalysisJob._meta.fields]


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = (
        "id", "space", "title", "origin", "assignment_mode", "created_at"
    )
    list_filter = ("origin", "assignment_mode")
    search_fields = ("note_key", "title", "content")
    readonly_fields = [field.name for field in Note._meta.fields]


@admin.register(NoteEvidence)
class NoteEvidenceAdmin(admin.ModelAdmin):
    list_display = ("id", "note", "message", "message_part", "reference_key")
    search_fields = ("reference_key",)
    readonly_fields = [field.name for field in NoteEvidence._meta.fields]


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("id", "space", "title", "status", "last_activity_at")
    list_filter = ("status",)
    search_fields = ("event_key", "title", "content")
    readonly_fields = [field.name for field in Event._meta.fields]


@admin.register(EventNote)
class EventNoteAdmin(admin.ModelAdmin):
    list_display = ("id", "event", "note", "created_by", "created_at")
    readonly_fields = [field.name for field in EventNote._meta.fields]


@admin.register(EventRelation)
class EventRelationAdmin(admin.ModelAdmin):
    list_display = (
        "id", "space", "left_event", "right_event", "relation_kind",
        "decision", "decided_at",
    )
    list_filter = ("relation_kind", "decision")
    search_fields = ("reason",)
    readonly_fields = [field.name for field in EventRelation._meta.fields]
