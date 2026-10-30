from rest_framework import serializers

from chat_analysis.models import (
    Event,
    EventRelation,
    Note,
    NoteEvidence,
    Report,
    ReportItem,
    ReportItemSource,
    ReportSection,
    EventSuggestion,
)


class NoteCreateSerializer(serializers.Serializer):
    note_key = serializers.CharField(max_length=255)
    title = serializers.CharField(max_length=500)
    content = serializers.CharField()
    start_at = serializers.DateTimeField(required=False, allow_null=True)
    end_at = serializers.DateTimeField(required=False, allow_null=True)
    analysis_job_id = serializers.IntegerField(
        min_value=1, required=False, allow_null=True
    )


class NoteUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=500, required=False)
    content = serializers.CharField(required=False)
    start_at = serializers.DateTimeField(required=False, allow_null=True)
    end_at = serializers.DateTimeField(required=False, allow_null=True)


class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = (
            "id",
            "uuid",
            "space_id",
            "created_by_id",
            "analysis_job_id",
            "note_key",
            "title",
            "content",
            "start_at",
            "end_at",
            "origin",
            "assignment_mode",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class NoteEvidenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NoteEvidence
        fields = (
            "id",
            "note_id",
            "message_id",
            "message_part_id",
            "reference_key",
            "created_at",
        )
        read_only_fields = fields


class EvidenceCreateSerializer(serializers.Serializer):
    message_id = serializers.IntegerField(min_value=1)
    message_part_id = serializers.IntegerField(
        min_value=1, required=False, allow_null=True
    )


class EventCreateSerializer(serializers.Serializer):
    event_key = serializers.CharField(max_length=255)
    title = serializers.CharField(max_length=500)
    content = serializers.CharField()
    status = serializers.ChoiceField(
        choices=Event.Status.choices,
        required=False,
        allow_null=True,
    )
    opened_at = serializers.DateTimeField(required=False, allow_null=True)
    last_activity_at = serializers.DateTimeField(
        required=False, allow_null=True
    )


class EventUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=500, required=False)
    content = serializers.CharField(required=False)
    status = serializers.ChoiceField(
        choices=Event.Status.choices,
        required=False,
        allow_null=True,
    )
    opened_at = serializers.DateTimeField(required=False, allow_null=True)
    last_activity_at = serializers.DateTimeField(
        required=False, allow_null=True
    )


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = (
            "id",
            "uuid",
            "space_id",
            "created_by_id",
            "event_key",
            "title",
            "content",
            "status",
            "opened_at",
            "last_activity_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class EventNoteSerializer(serializers.Serializer):
    note_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=True,
    )


class EventRelationCreateSerializer(serializers.Serializer):
    left_event_id = serializers.IntegerField(min_value=1)
    right_event_id = serializers.IntegerField(min_value=1)
    relation_kind = serializers.ChoiceField(
        choices=EventRelation.RelationKind.choices
    )
    decision = serializers.ChoiceField(
        choices=EventRelation.Decision.choices,
        required=False,
        default=EventRelation.Decision.PENDING,
    )
    reason = serializers.CharField(required=False, allow_blank=True)
    source_note_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        default=list,
    )

    def validate(self, attrs):
        if attrs["left_event_id"] == attrs["right_event_id"]:
            raise serializers.ValidationError(
                {"right_event_id": "An event cannot relate to itself."}
            )
        return attrs


class EventRelationSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventRelation
        fields = (
            "id",
            "space_id",
            "left_event_id",
            "right_event_id",
            "relation_kind",
            "decision",
            "reason",
            "source_note_ids",
            "created_by_id",
            "decided_by_id",
            "decided_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ReportCreateSerializer(serializers.Serializer):
    request_key = serializers.CharField(max_length=255)
    title = serializers.CharField(max_length=500)
    period_start = serializers.DateTimeField(required=False, allow_null=True)
    period_end = serializers.DateTimeField(required=False, allow_null=True)
    body_format = serializers.ChoiceField(
        choices=Report.BodyFormat.choices,
        required=False,
        default=Report.BodyFormat.MARKDOWN,
    )

    def validate_request_key(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("request_key is required.")
        return value

    def validate(self, attrs):
        if (
            attrs.get("period_start")
            and attrs.get("period_end")
            and attrs["period_end"] < attrs["period_start"]
        ):
            raise serializers.ValidationError(
                {"period_end": "period_end must be after period_start."}
            )
        return attrs


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = (
            "id",
            "uuid",
            "space_id",
            "created_by_id",
            "request_key",
            "previous_report_id",
            "title",
            "period_start",
            "period_end",
            "body_format",
            "body",
            "source_info",
            "content",
            "snapshot_ref",
            "processing",
            "status",
            "generated_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ReportItemSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportItemSource
        fields = (
            "id",
            "reference_key",
            "source_kind",
            "event_id",
            "note_id",
            "reference_url",
            "display_text",
            "event_snapshot",
            "note_snapshot",
        )
        read_only_fields = fields


class ReportItemSerializer(serializers.ModelSerializer):
    sources = ReportItemSourceSerializer(many=True, read_only=True)

    class Meta:
        model = ReportItem
        fields = (
            "id",
            "section_id",
            "position",
            "title",
            "summary",
            "label",
            "time_text",
            "contact_text",
            "followup_text",
            "followup_kind",
            "display_kind",
            "sources",
        )
        read_only_fields = fields


class ReportSectionSerializer(serializers.ModelSerializer):
    items = ReportItemSerializer(many=True, read_only=True)

    class Meta:
        model = ReportSection
        fields = ("id", "section_key", "title", "position", "items")
        read_only_fields = fields


class EventSuggestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventSuggestion
        fields = (
            "id",
            "space_id",
            "analysis_job_id",
            "note_id",
            "event_id",
            "event_key",
            "title",
            "summary",
            "status",
            "created_by_id",
            "reviewed_by_id",
            "reviewed_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields
