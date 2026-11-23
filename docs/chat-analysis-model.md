# Chat analysis model

Chat event analysis uses the global default model unless `CHAT_ANALYSIS_MODEL_UUID`
is set in the analysis worker's environment. Set it to the UUID of an active LLM
configuration to select that model for note and event extraction, without changing
the global default used by other features. The input budget uses the same model.

The setting selects a model; it does not automatically fail over when a provider
fails. After changing it, recreate the analysis worker using the normal deployment
process and verify a test analysis. Existing failed jobs require a separate retry.

## Personal relevance in the event API

The event list and detail responses include two viewer-specific fields.

| Field | Meaning |
| --- | --- |
| `viewer_relevance` | `my_todo` when the viewer has an explicit unfinished action, `related` when there is evidence of involvement, or `other` when there is insufficient evidence |
| `viewer_evidence_message_ids` | Original message IDs that support the returned label, available in the event detail's `evidence` list |

Event `status` still describes progress on the shared event. Use both fields
when displaying an event. A missing personal field from older servers can
be rendered with the event's progress alone. An open event can be relevant
to several people, and one person's action can finish while another remains.

The migration adds identity and action evidence tables. It leaves existing
messages, events, and checkpoints intact. The server can recognize prior
participation when a completed upload ties the viewer's account to an exact
outgoing sender. Historical events without assignment evidence acquire
personal actions as future analysis produces that evidence.
