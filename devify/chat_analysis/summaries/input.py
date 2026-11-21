"""Build a compact, lossless model view of a reviewed summary snapshot."""

import json
from datetime import datetime
from datetime import timezone as utc_timezone

from django.utils import timezone


def summary_content(record):
    # Names and conversation identities repeat in the transport format.
    # Keep display names once; database IDs carry no meaning for the model.
    # for the summary. Every original text and its timestamp remain present.
    speakers = []
    speaker_ids = {}
    chats = {}
    for message in record.input_messages:
        sender = message["sender"]
        if sender not in speaker_ids:
            speaker_ids[sender] = len(speakers)
            speakers.append(sender)
        chat = chats.setdefault(
            message["username"], {"name": message["display"], "messages": []}
        )
        local_time = timezone.localtime(
            datetime.fromtimestamp(message["time"], utc_timezone.utc)
        )
        chat["messages"].append(
            [
                local_time.isoformat(timespec="seconds"),
                speaker_ids[sender],
                message["text"],
            ]
        )
    return json.dumps(
        {
            "title": record.title,
            "range": record.range_label,
            "language": record.language,
            "speakers": speakers,
            "chats": list(chats.values()),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
