"""Redis/worker inspection is read-only and fails closed for recovery."""

import base64
import json
from unittest.mock import MagicMock

from threadline.services import workflow_recovery as recovery


def message(email_id):
    return {
        "headers": {"task": recovery.WORKFLOW_TASK},
        "properties": {"body_encoding": "base64"},
        "body": base64.b64encode(
            json.dumps([[email_id], {}, None]).encode()
        ).decode(),
    }


def test_inspection_includes_queued_unacked_and_worker_requests(monkeypatch):
    app = MagicMock()
    app.amqp.queues = {"celery": None}
    connection = app.connection_for_read.return_value.__enter__.return_value
    connection.transport.driver_type = "redis"
    channel = connection.channel.return_value
    channel.priority_steps = [0, 3]
    channel._q_for_pri.side_effect = lambda queue, pri: f"{queue}:{pri}"
    queued_merge = message(1)
    queued_merge['headers']['task'] = recovery.MERGE_TASK
    channel.client.lrange.side_effect = [[json.dumps(queued_merge)], []]
    channel.client.hvals.return_value = [
        json.dumps([message(2), "", "celery"])
    ]
    inspector = app.control.inspect.return_value
    inspector.active_queues.return_value = {"worker": [{"name": "celery"}]}
    app.amqp.router.route.return_value = {
        "queue": type("Queue", (), {"name": "celery"})()
    }
    inspector.active.return_value = {
        "worker": [{"name": recovery.WORKFLOW_TASK, "args": [3]}]
    }
    inspector.reserved.return_value = {
        "worker": [{"name": recovery.WORKFLOW_TASK, "args": "[4]"}]
    }
    inspector.scheduled.return_value = {
        "worker": [
            {
                "request": {
                    "name": recovery.WORKFLOW_TASK,
                    "kwargs": {"email_id": 5},
                }
            }
        ]
    }
    monkeypatch.setattr(recovery, "current_app", app)
    assert recovery.workflows_in_flight() == {"1", "2", "3", "4", "5"}
    channel.client.lrem.assert_not_called()
    channel.client.lpop.assert_not_called()


def test_unavailable_broker_postpones_recovery(monkeypatch):
    app = MagicMock()
    app.connection_for_read.side_effect = ConnectionError("redis unavailable")
    monkeypatch.setattr(recovery, "current_app", app)
    assert recovery.workflows_in_flight() is None


def test_chat_only_inspection_cannot_authorize_email_recovery(monkeypatch):
    app = MagicMock()
    connection = app.connection_for_read.return_value.__enter__.return_value
    connection.transport.driver_type = "redis"
    inspector = app.control.inspect.return_value
    inspector.active_queues.return_value = {
        "chat-worker": [{"name": "chat_analysis"}],
    }
    app.amqp.router.route.return_value = {
        "queue": type("Queue", (), {"name": "celery"})()
    }
    monkeypatch.setattr(recovery, "current_app", app)
    assert recovery.workflows_in_flight() is None


def test_missing_mail_worker_reply_postpones_recovery(monkeypatch):
    app = MagicMock()
    connection = app.connection_for_read.return_value.__enter__.return_value
    connection.transport.driver_type = 'redis'
    inspector = app.control.inspect.return_value
    inspector.active_queues.return_value = {'mail': [{'name': 'celery'}]}
    app.amqp.router.route.return_value = {
        'queue': type('Queue', (), {'name': 'celery'})(),
    }
    inspector.active.return_value = {'chat-worker': []}
    monkeypatch.setattr(recovery, 'current_app', app)
    assert recovery.workflows_in_flight() is None


def test_merge_and_retry_wrappers_are_inflight_email_work():
    assert (
        recovery._email_id({"name": recovery.MERGE_TASK, "args": [41]}) == "41"
    )
    assert (
        recovery._email_id({"name": recovery.RETRY_TASK, "args": [42]}) == "42"
    )
