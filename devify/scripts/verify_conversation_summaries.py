"""Verify summaries in the existing dev DB and roll back all fixtures."""

import copy
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework.test import APIClient

from billing.entitlements import build_entitlements
from chat_analysis.models import ChatSummary
from spaces.models import SpaceMembership

checks = []
with transaction.atomic():
    user = get_user_model().objects.create_user(
        username=f"summary-verify-{uuid.uuid4().hex[:12]}"
    )
    # Registration bootstraps the user's personal space in this project.
    space = user.owned_spaces.filter(kind="personal").first()
    if not space:
        from spaces.models import Space

        space = Space.objects.create(
            name="Summary verification",
            slug=f"summary-{uuid.uuid4().hex}",
            kind="personal",
            owner=user,
            personal_owner=user,
            created_by=user,
        )
        SpaceMembership.objects.create(space=space, user=user, role="owner")
    client = APIClient()
    client.force_authenticate(user)
    url = f"/api/v1/spaces/{space.pk}/chat-summaries"
    now = timezone.now().replace(microsecond=0)
    payload = dict(
        request_key=str(uuid.uuid4()),
        platform="wechat",
        source_namespace="verify-source",
        source_conversation_id="verify-chat",
        title="Verification chat",
        range_label="Today",
        mode="time",
        period_start=(now - timedelta(hours=1)).isoformat(),
        period_end=now.isoformat(),
        messages=[
            dict(
                username="verify-chat",
                display="Verification chat",
                sender="Tester",
                time=int(now.timestamp()) - 5,
                text="The delivery plan was confirmed today.",
            )
        ],
    )
    result = client.post(url, payload, format="json")
    assert result.status_code == 202, (result.status_code, result.data)
    record_id = result.data["data"]["id"]
    checks.append("ordinary user can submit a cloud summary")
    assert "cloud.chat_summary" in build_entitlements(user)["features"]
    checks.append("ordinary entitlement includes cloud summary")
    repeated = client.post(url, payload, format="json")
    assert (
        repeated.status_code == 200
        and repeated.data["data"]["id"] == record_id
    )
    assert ChatSummary.objects.filter(created_by=user).count() == 1
    checks.append("identical request is idempotent")
    changed = copy.deepcopy(payload)
    changed["messages"][0]["text"] = "Changed"
    assert client.post(url, changed, format="json").status_code == 409
    checks.append("request-key payload conflicts are rejected")
    invalid = copy.deepcopy(payload)
    invalid["request_key"] = str(uuid.uuid4())
    invalid["period_start"] = (now - timedelta(days=8)).isoformat()
    assert client.post(url, invalid, format="json").status_code == 400
    invalid = copy.deepcopy(payload)
    invalid["messages"][0]["username"] = "other-chat"
    assert client.post(url, invalid, format="json").status_code == 400
    checks.append("date and primary-conversation boundaries are enforced")
    detail = f"{url}/{record_id}"
    assert client.delete(detail).status_code == 400
    checks.append("running work cannot be deleted")
    other = get_user_model().objects.create_user(
        username=f"summary-outsider-{uuid.uuid4().hex[:12]}"
    )
    client.force_authenticate(other)
    assert client.get(detail).status_code == 404
    SpaceMembership.objects.create(space=space, user=other, role="user")
    assert client.get(detail).status_code == 404
    assert client.get(url).data["data"]["list"] == []
    checks.append(
        "another user, even in the same space, cannot read the snapshot"
    )
    client.force_authenticate(None)
    assert client.get(url).status_code in (401, 403)
    checks.append("anonymous access is rejected")
    client.force_authenticate(user)
    ChatSummary.objects.filter(pk=record_id).update(status="failed")
    assert client.post(detail).status_code == 202
    assert client.post(detail).status_code == 200
    checks.append("retry is an idempotent queued transition")
    ChatSummary.objects.filter(pk=record_id).update(
        status="ready", body="## Result\nDone"
    )
    assert client.delete(detail).status_code == 204
    assert not ChatSummary.objects.filter(pk=record_id).exists()
    checks.append("terminal summaries can be deleted")
    for _ in range(3):
        row = copy.deepcopy(payload)
        row["request_key"] = str(uuid.uuid4())
        assert client.post(url, row, format="json").status_code == 202
    row = copy.deepcopy(payload)
    row["request_key"] = str(uuid.uuid4())
    assert client.post(url, row, format="json").status_code == 429
    checks.append("pending task admission is bounded")
    ChatSummary.objects.filter(created_by=user).update(
        updated_at=now - timedelta(minutes=16)
    )
    assert client.get(url).status_code == 200
    assert not ChatSummary.objects.filter(
        created_by=user, status__in=["queued", "running"]
    ).exists()
    checks.append(
        "abandoned work becomes retryable instead of polling forever"
    )
    from chat_analysis.summaries.tasks import generate_chat_summary

    worker_record = ChatSummary.objects.filter(created_by=user).first()
    ChatSummary.objects.filter(pk=worker_record.pk).update(status="queued")
    with patch(
        "chat_analysis.summaries.tasks.LLMTracker.call_and_track",
        return_value=("## Verified result", {"model": "test"}),
    ) as model:
        generate_chat_summary.run(
            worker_record.pk, str(worker_record.dispatch_token)
        )
        generate_chat_summary.run(
            worker_record.pk, str(worker_record.dispatch_token)
        )
        assert model.call_count == 1
    worker_record.refresh_from_db()
    assert (
        worker_record.status == "ready" and worker_record.input_messages == []
    )
    checks.append(
        "duplicate worker deliveries call the model once and clear raw input"
    )
    candidate = (
        ChatSummary.objects.filter(created_by=user)
        .exclude(pk=worker_record.pk)
        .first()
    )
    ChatSummary.objects.filter(pk=candidate.pk).update(status="queued")
    with (
        patch(
            "chat_analysis.summaries.tasks.request_budget",
            return_value=(1, lambda *_: 2),
        ),
        patch(
            "chat_analysis.summaries.tasks.LLMTracker.call_and_track"
        ) as model,
    ):
        generate_chat_summary.run(candidate.pk, str(candidate.dispatch_token))
        assert not model.called
    candidate.refresh_from_db()
    assert candidate.status == "failed" and "范围" in candidate.error
    checks.append(
        "oversized model input fails clearly before calling the provider"
    )
    transaction.set_rollback(True)
print(
    {
        "passed": len(checks),
        "checks": checks,
        "fixtures": "rolled back; no test database created",
    }
)
