"""Integration tests for the admin conversation management API."""
import uuid

import pytest
from agentcore_task.adapters.django.models import TaskExecution
from agentcore_task.adapters.django.services import register_task_execution
from django.contrib.auth.models import User
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

from threadline.models import EmailMessage


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username=f"admin-{uuid.uuid4().hex[:8]}",
        email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
        password="adminpass",
    )


@pytest.fixture
def staff_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture
def threadline_user(db):
    return User.objects.create_user(
        username=f"user-{uuid.uuid4().hex[:8]}",
        email=f"user-{uuid.uuid4().hex[:8]}@example.com",
        password="userpass",
    )


@pytest.fixture
def conversation(threadline_user):
    return EmailMessage.objects.create(
        user=threadline_user,
        message_id=f"msg-{uuid.uuid4().hex[:8]}@example.com",
        subject="Admin conversation smoke test",
        sender="sender@example.com",
        recipients="user@example.com",
        received_at=timezone.now(),
        text_content="hello from admin api",
        summary_title="Summary title",
        summary_content="Summary content",
        metadata={"source": "integration-test"},
    )


@pytest.mark.django_db
@pytest.mark.integration
class TestAdminConversationAPI:
    def test_list_returns_conversations_with_user(
        self, staff_client, conversation
    ):
        response = staff_client.get("/api/v1/admin/threadline/conversations/")

        assert response.status_code == 200
        body = response.json()["data"]
        assert body["pagination"]["total"] >= 1
        row = next(
            item
            for item in body["list"]
            if item["uuid"] == str(conversation.uuid)
        )
        assert row["user"]["id"] == conversation.user_id
        assert row["user_display"] == conversation.user.username

    def test_detail_returns_full_conversation(
        self, staff_client, conversation
    ):
        response = staff_client.get(
            f"/api/v1/admin/threadline/conversations/{conversation.uuid}/"
        )

        assert response.status_code == 200
        body = response.json()["data"]
        assert body["id"] == conversation.id
        assert body["user"]["id"] == conversation.user_id
        assert body["summary_title"] == "Summary title"

    def test_tasks_list_returns_related_executions(
        self, staff_client, conversation
    ):
        task = register_task_execution(
            task_id="task-for-email-001",
            task_name="threadline.workflow",
            module="threadline",
            created_by=conversation.user,
            metadata={
                "context": {
                    "email_id": str(conversation.id),
                    "user_id": str(conversation.user_id),
                }
            },
        )

        response = staff_client.get(
            "/api/v1/admin/threadline/conversations/"
            f"{conversation.uuid}/tasks/"
        )

        assert response.status_code == 200
        body = response.json()["data"]
        items = body["list"]
        assert any(item["task_id"] == task.task_id for item in items)

    def test_tasks_detail_returns_related_execution(
        self, staff_client, conversation
    ):
        task = register_task_execution(
            task_id="task-for-email-002",
            task_name="threadline.workflow.detail",
            module="threadline",
            created_by=conversation.user,
            metadata={
                "context": {
                    "email_id": str(conversation.id),
                    "user_id": str(conversation.user_id),
                }
            },
        )

        response = staff_client.get(
            "/api/v1/admin/threadline/conversations/"
            f"{conversation.uuid}/tasks/{task.id}/"
        )

        assert response.status_code == 200
        body = response.json()["data"]
        assert body["id"] == task.id
        assert body["task_id"] == task.task_id

    def test_tasks_use_conversation_key_for_count_and_pages(
        self, staff_client, conversation
    ):
        prefix = f"/api/v1/admin/threadline/conversations/{conversation.uuid}"
        tasks = []
        values = [
            conversation.pk, str(conversation.pk), f"{conversation.pk} ",
            f"0{conversation.pk}", float(conversation.pk), None,
        ]
        for number, value in enumerate(values):
            tasks.append(
                register_task_execution(
                    task_id=f"historical-{number}",
                    task_name="threadline.workflow",
                    module="threadline",
                    metadata={"context": {"email_id": value}},
                )
            )
        task_ids = [task.pk for task in tasks]
        TaskExecution.objects.filter(id__in=task_ids).update(
            created_at=timezone.now(),
        )

        task_queries = []

        def capture(execute, sql, params, many, context):
            if "FROM `agentcore_task_execution`" in sql:
                task_queries.append(sql)
            return execute(sql, params, many, context)

        with connection.execute_wrapper(capture):
            response = staff_client.get(
                f"{prefix}/tasks/", {"page": 1, "page_size": 2}
            )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["pagination"]["total"] == 3
        assert [row["id"] for row in data["list"]] == [
            tasks[2].id, tasks[1].id,
        ]
        page = staff_client.get(
            f"{prefix}/tasks/", {"page": 2, "page_size": 2}
        )
        assert [row["id"] for row in page.json()["data"]["list"]] == [
            tasks[0].id
        ]
        assert staff_client.get(
            f"{prefix}/tasks/{tasks[3].id}/"
        ).status_code == 404
        assert len(task_queries) == 2
        assert all("threadline_email_key" in sql for sql in task_queries)
        assert all("JSON_EXTRACT" not in sql for sql in task_queries)

    def test_tasks_list_returns_empty_page(self, staff_client, conversation):
        prefix = f"/api/v1/admin/threadline/conversations/{conversation.uuid}"
        response = staff_client.get(f"{prefix}/tasks/")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["pagination"]["total"] == 0
        assert data["list"] == []
