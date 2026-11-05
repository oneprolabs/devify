"""Regression tests for undated TODO visibility (issue #118)."""

from datetime import datetime, timezone
from uuid import uuid4

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from threadline.models import EmailTodo
from threadline.views.email_todo import EmailTodoAPIView


class TestTodoDeadlineVisibility(TestCase):
    """Use transaction-scoped data without changing existing user TODOs."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create(username=f"todo118-{uuid4().hex}")
        cls.other_user = User.objects.create(username=f"todo118-{uuid4().hex}")
        cls.in_range = EmailTodo.objects.create(
            user=cls.user,
            content="Issue 118 dated TODO",
            deadline=datetime(2026, 11, 20, tzinfo=timezone.utc),
        )
        cls.undated = EmailTodo.objects.create(
            user=cls.user,
            content="Issue 118 undated TODO",
            priority="high",
            owner="Reviewer",
        )
        cls.completed = EmailTodo.objects.create(
            user=cls.user,
            content="Issue 118 completed TODO",
            is_completed=True,
        )
        cls.out_of_range = EmailTodo.objects.create(
            user=cls.user,
            content="Issue 118 October TODO",
            deadline=datetime(2026, 10, 15, tzinfo=timezone.utc),
        )
        cls.foreign = EmailTodo.objects.create(
            user=cls.other_user, content="Issue 118 private TODO"
        )

    def get_ids(self, **params):
        request = APIRequestFactory().get("/api/v1/todos", params)
        force_authenticate(request, user=self.user)
        response = EmailTodoAPIView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        data = response.data["data"]
        self.assertEqual(data["pagination"]["total"], len(data["list"]))
        return {row["id"] for row in data["list"]}

    def range_params(self, **params):
        return {
            "deadline_after": "2026-11-01T00:00:00Z",
            "deadline_before": "2026-11-30T23:59:59Z",
            **params,
        }

    def test_deadline_range_remains_strict_by_default(self):
        self.assertEqual(
            self.get_ids(**self.range_params()), {self.in_range.id}
        )
        self.assertEqual(
            self.get_ids(**self.range_params(include_no_deadline="false")),
            {self.in_range.id},
        )

    def test_list_includes_undated_but_not_out_of_range_or_foreign(self):
        self.assertEqual(
            self.get_ids(**self.range_params(include_no_deadline="true")),
            {self.in_range.id, self.undated.id, self.completed.id},
        )

    def test_undated_todos_still_obey_status_priority_owner_and_search(self):
        params = self.range_params(include_no_deadline="true")
        for filters, expected in [
            ({"is_completed": "true"}, {self.completed.id}),
            ({"is_completed": "false"}, {self.in_range.id, self.undated.id}),
            ({"priority": "high"}, {self.undated.id}),
            ({"owner": "Reviewer"}, {self.undated.id}),
            ({"search": "undated"}, {self.undated.id}),
            ({"search": "private"}, set()),
        ]:
            with self.subTest(filters=filters):
                self.assertEqual(self.get_ids(**params, **filters), expected)

    def test_single_sided_ranges_can_include_undated_todos(self):
        for bound, value in [
            ("deadline_after", "2026-11-01T00:00:00Z"),
            ("deadline_before", "2026-11-30T23:59:59Z"),
        ]:
            with self.subTest(bound=bound):
                ids = self.get_ids(
                    **{bound: value, "include_no_deadline": "true"}
                )
                self.assertIn(self.undated.id, ids)
                self.assertNotIn(self.foreign.id, ids)

    def test_unbounded_query_is_unchanged(self):
        expected = {
            self.in_range.id, self.undated.id,
            self.completed.id, self.out_of_range.id,
        }
        self.assertEqual(self.get_ids(), expected)
        self.assertEqual(self.get_ids(include_no_deadline="true"), expected)

    def test_new_undated_todo_is_returned_by_list_query(self):
        request = APIRequestFactory().post(
            "/api/v1/todos",
            {"content": "Issue 118 newly created"},
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = EmailTodoAPIView.as_view()(request)
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.data["data"]["deadline"])
        self.assertIn(
            response.data["data"]["id"],
            self.get_ids(**self.range_params(include_no_deadline="true")),
        )
