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
outgoing sender. Use `backfill_chat_identities --space-id <uuid>` to
preview identities that can be recovered from completed archives. Add
`--apply` to store those identities. Historical events without
assignment evidence acquire personal actions as future analysis
produces that evidence.

The event list accepts `viewer_relevance=my_todo|related|other`. It applies
the label before pagination. Pass `include_relevance_counts=true` to return
`data.relevance_counts` without selecting a label. A request with a label
also returns the three counts. Counts use all events visible to the
current user that match the status, tag and conversation filters, before
applying the keyword or selected relevance label.

`GET /api/v1/spaces/{space_id}/events` accepts `q` for a case-insensitive
substring search in the event title or content. The server trims surrounding
whitespace, ignores an empty query, and returns HTTP 400 for a trimmed query
longer than 200 Unicode characters. `pagination.total` includes only events
matching the keyword and selected relevance label. Results are ordered by
`-last_activity_at, -id`. Every successful event list response includes
`data.search_supported: true`, including when the list is empty.

The MariaDB migration also gives the new foreign keys database-level
delete cascades. An older image can then delete a merged message or a
suggestion during a blue/green rollback. Evidence for a deleted source
is removed if the old image has no code to move it to the survivor.
