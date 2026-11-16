"""Verify production API and workers use the same durable chat storage."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class ChatStorageComposeTest(unittest.TestCase):
    def test_production_and_bluegreen_share_chat_storage(self):
        with tempfile.TemporaryDirectory() as temporary:
            env_file = Path(temporary) / "empty.env"
            env_file.touch()
            env = os.environ.copy()
            env.update(
                DEVIFY_ENV_FILE=str(env_file), DEVIFY_RUNTIME_ROOT=temporary
            )
            variants = (
                (
                    ["-f", "docker-compose.yml"],
                    ["devify-api", "devify-worker", "devify-chat-worker"],
                ),
                (
                    [
                        "-f",
                        "docker-compose.yml",
                        "-f",
                        "deploy/docker-compose.yml",
                        "-f",
                        "docker-compose.bluegreen.yml",
                        "--profile",
                        "blue",
                        "--profile",
                        "green",
                    ],
                    [
                        "devify-api-blue", "devify-api-green", "devify-worker",
                        "devify-chat-worker",
                    ],
                ),
            )
            for args, services in variants:
                output = subprocess.check_output(
                    ["docker", "compose", *args, "config", "--format", "json"],
                    cwd=ROOT,
                    env=env,
                    text=True,
                    stderr=subprocess.PIPE,
                )
                config = json.loads(output)
                self.assertNotEqual(
                    config["services"]["devify-worker"]["environment"].get(
                        "CHAT_DEDICATED_WORKER", "false"
                    ).lower(),
                    "true",
                )
                self.assertEqual(
                    config["services"]["devify-worker"]["command"], ["celery"]
                )
                self.assertIn(
                    "--queues=chat_ingestion",
                    config["services"]["devify-chat-worker"]["command"],
                )
                analysis = config["services"]["devify-analysis-worker"]
                self.assertIn("--queues=chat_analysis", analysis["command"])
                self.assertIn("--concurrency=1", analysis["command"])
                for name in (
                    "CHAT_ANALYSIS_LLM_ENABLED",
                    "CHAT_ANALYSIS_AUTO_CREATE_EVENTS",
                    "CHAT_UPLOAD_DEDICATED_QUEUE",
                ):
                    self.assertEqual(analysis["environment"][name], "true")
                api_services = (
                    name for name in services if name.startswith("devify-api")
                )
                for service in api_services:
                    self.assertEqual(
                        config["services"][service]["depends_on"]
                        ["devify-chat-worker"]["condition"],
                        "service_started",
                    )
                for service in services:
                    self.assertEqual(
                        config["services"][service]["environment"].get(
                            "CHAT_UPLOAD_DEDICATED_QUEUE"
                        ),
                        "true",
                    )
                for service in services:
                    mounts = {
                        mount["target"]: mount["source"]
                        for mount in config["services"][service].get(
                            "volumes", []
                        )
                    }
                    for name in (
                        "chat_upload_archives",
                        "chat_media",
                        "chat_avatars",
                    ):
                        self.assertEqual(
                            mounts.get(f"/opt/devify/{name}"),
                            str(Path(temporary) / "data" / name),
                            f"{service}: {name}",
                        )


if __name__ == "__main__":
    unittest.main()
