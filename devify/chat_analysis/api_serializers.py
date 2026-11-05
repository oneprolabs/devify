from rest_framework import serializers

from chat_analysis.models import (
    Event,
    EventEvidence,
    EventRelation,
    EventSuggestion,
    EventTag,
    EventTagAssignment,
    Note,
    NoteEvidence,
    QuestionAnswer,
    Report,
    ReportItem,
    ReportItemSource,
    ReportSection,
    TopicSubscription,
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
            "structured_data",
            "start_at",
            "end_at",
            "origin",
            "assignment_mode",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class NoteEvidenceSerializer(serializers.ModelSerializer):
    conversation_id = serializers.IntegerField(
        source="message.conversation_id", read_only=True
    )
    sender_name = serializers.CharField(
        source="message.sender_name", read_only=True
    )
    occurred_at = serializers.DateTimeField(
        source="message.occurred_at", read_only=True
    )

    class Meta:
        model = NoteEvidence
        fields = (
            "id",
            "note_id",
            "message_id",
            "message_part_id",
            "reference_key",
            "conversation_id",
            "sender_name",
            "occurred_at",
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
    tags = serializers.SerializerMethodField()

    def get_tags(self, obj):
        assignments = getattr(obj, "_prefetched_objects_cache", {}).get(
            "tag_assignments", obj.tag_assignments.all()
        )
        return EventTagSerializer(
            [assignment.tag for assignment in assignments], many=True
        ).data

    class Meta:
        model = Event
        fields = (
            "id",
            "uuid",
            "space_id",
            "created_by_id",
            "event_key",
            "entity_key",
            "title",
            "content",
            "status",
            "opened_at",
            "last_activity_at",
            "created_at",
            "updated_at",
            "tags",
        )
        read_only_fields = fields


class EventEvidenceSerializer(serializers.ModelSerializer):
    conversation_id = serializers.IntegerField(
        source="message.conversation_id", read_only=True
    )
    sender_name = serializers.CharField(
        source="message.sender_name", read_only=True
    )
    occurred_at = serializers.DateTimeField(
        source="message.occurred_at", read_only=True
    )
    ingest_seq = serializers.IntegerField(
        source="message.ingest_seq", read_only=True
    )

    class Meta:
        model = EventEvidence
        fields = (
            "id",
            "event_id",
            "message_id",
            "conversation_id",
            "sender_name",
            "occurred_at",
            "ingest_seq",
            "created_at",
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
            "entity_key",
            "title",
            "summary",
            "proposed_status",
            "proposed_tags",
            "source_seqs",
            "status",
            "created_by_id",
            "reviewed_by_id",
            "reviewed_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class TopicSubscriptionCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    instruction = serializers.CharField(max_length=5000)
    filters = serializers.DictField(required=False, default=dict)
    include_open = serializers.BooleanField(required=False, default=True)
    period = serializers.ChoiceField(
        choices=TopicSubscription.Period.choices,
        required=False,
        default=TopicSubscription.Period.WEEK,
    )
    time_local = serializers.TimeField(required=False, allow_null=True)
    timezone = serializers.CharField(
        max_length=64, required=False, default="Asia/Shanghai"
    )
    enabled = serializers.BooleanField(required=False, default=True)

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Title is required.")
        return value

    def validate_instruction(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Instruction is required.")
        return value

    def validate_filters(self, value):
        allowed = {
            "event_ids",
            "note_ids",
            "conversation_ids",
            "tag_keys",
            "keywords",
        }
        unknown = set(value) - allowed
        if unknown:
            raise serializers.ValidationError(
                {key: "Unsupported filter." for key in sorted(unknown)}
            )
        for key in ("event_ids", "note_ids", "conversation_ids"):
            if key in value and (
                not isinstance(value[key], list)
                or any(
                    not isinstance(item, int) or item < 1
                    for item in value[key]
                )
            ):
                raise serializers.ValidationError(
                    {key: "Must be a list of positive integers."}
                )
        for key in ("tag_keys", "keywords"):
            if key in value and (
                not isinstance(value[key], list)
                or any(
                    not isinstance(item, str) or not item.strip()
                    for item in value[key]
                )
            ):
                raise serializers.ValidationError(
                    {key: "Must be a list of non-empty strings."}
                )
        return value


class TopicSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TopicSubscription
        fields = (
            "id",
            "space_id",
            "created_by_id",
            "title",
            "instruction",
            "filters",
            "include_open",
            "period",
            "time_local",
            "timezone",
            "enabled",
            "last_run_at",
            "last_error",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class QuestionCreateSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=2000)
    event_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        default=list,
    )
    note_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        default=list,
    )
    conversation_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        default=list,
    )
    tag_keys = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        default=list,
    )
    keywords = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        default=list,
    )

    def validate_question(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Question is required.")
        return value


class QuestionAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionAnswer
        fields = (
            "id",
            "uuid",
            "space_id",
            "created_by_id",
            "question",
            "scope",
            "answer",
            "citations",
            "usage",
            "status",
            "error",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class EventTagCreateSerializer(serializers.Serializer):
    tag_key = serializers.CharField(max_length=120, required=False)
    label = serializers.CharField(max_length=120)

    def validate(self, attrs):
        label = attrs["label"].strip()
        if not label:
            raise serializers.ValidationError({"label": "Label is required."})
        key = attrs.get("tag_key", "").strip() or label.casefold()
        attrs["label"] = label
        attrs["tag_key"] = key
        return attrs


class EventTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventTag
        fields = (
            "id",
            "space_id",
            "created_by_id",
            "tag_key",
            "label",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class EventTagAssignmentCreateSerializer(serializers.Serializer):
    tag_id = serializers.IntegerField(min_value=1)


class EventTagAssignmentSerializer(serializers.ModelSerializer):
    tag = EventTagSerializer(read_only=True)

    class Meta:
        model = EventTagAssignment
        fields = (
            "id",
            "event_id",
            "tag_id",
            "tag",
            "created_by_id",
            "created_at",
        )
        read_only_fields = fields
