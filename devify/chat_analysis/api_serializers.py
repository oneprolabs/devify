from rest_framework import serializers

from chat_analysis.models import Event, EventRelation, Note, NoteEvidence


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
