# API Reference

## Base URL

```
https://api.aimychats.com/v1
```

All API requests must use HTTPS. Include your API key in the `Authorization` header.

## Conversations

### List Conversations

Get a paginated list of conversations.

```http
GET /conversations
```

**Query parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `page` | integer | Page number (default: 1) |
| `per_page` | integer | Items per page (default: 20, max: 100) |
| `status` | string | Filter by status: `processing`, `completed`, `failed` |
| `source` | string | Filter by source: `email`, `whatsapp`, `api` |
| `search` | string | Search in title and content |
| `sort` | string | Sort by: `created_at`, `updated_at` (default: `-created_at`) |

**Example request:**

```bash
curl -X GET "https://api.aimychats.com/v1/conversations?page=1&per_page=20&status=completed" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Response:**

```json
{
  "data": [
    {
      "id": "conv_123",
      "title": "Customer inquiry about pricing",
      "source": "email",
      "status": "completed",
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:05:00Z",
      "summary": {
        "title": "Pricing inquiry",
        "content": "Customer asked about professional plan pricing...",
        "sentiment": "neutral",
        "topics": ["pricing", "features"]
      }
    }
  ],
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 45,
    "total_pages": 3
  }
}
```

### Get Conversation

Retrieve a specific conversation.

```http
GET /conversations/{id}
```

**Example request:**

```bash
curl -X GET "https://api.aimychats.com/v1/conversations/conv_123" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Response:**

```json
{
  "id": "conv_123",
  "title": "Customer inquiry about pricing",
  "content": "Full conversation content...",
  "source": "email",
  "status": "completed",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:05:00Z",
  "summary": {
    "title": "Pricing inquiry",
    "content": "Customer asked about professional plan pricing...",
    "sentiment": "neutral",
    "topics": ["pricing", "features"],
    "action_items": ["Send pricing sheet", "Schedule demo"]
  },
  "attachments": [
    {
      "id": "att_123",
      "filename": "requirements.pdf",
      "size": 102400,
      "url": "https://storage.aimychats.com/att_123"
    }
  ]
}
```

### Create Conversation

Create a new conversation.

```http
POST /conversations
```

**Request body:**

```json
{
  "title": "Meeting notes",
  "content": "Discussion about Q1 goals...",
  "source": "api",
  "metadata": {
    "participants": ["john@example.com", "jane@example.com"],
    "date": "2024-01-01"
  }
}
```

**Response:**

```json
{
  "id": "conv_124",
  "title": "Meeting notes",
  "content": "Discussion about Q1 goals...",
  "source": "api",
  "status": "processing",
  "created_at": "2024-01-01T10:00:00Z",
  "summary": null
}
```

### Update Conversation

Update an existing conversation.

```http
PATCH /conversations/{id}
```

**Request body:**

```json
{
  "title": "Updated meeting notes",
  "metadata": {
    "reviewed": true
  }
}
```

### Delete Conversation

Delete a conversation permanently.

```http
DELETE /conversations/{id}
```

**Response:**

```json
{
  "deleted": true,
  "id": "conv_123"
}
```

## Search

### Search Conversations

Perform advanced search across conversations.

```http
POST /conversations/search
```

**Request body:**

```json
{
  "query": "pricing features",
  "filters": {
    "date_from": "2024-01-01",
    "date_to": "2024-01-31",
    "topics": ["pricing"],
    "sentiment": "positive"
  },
  "sort": "relevance",
  "page": 1,
  "per_page": 20
}
```

**Response:**

```json
{
  "data": [
    {
      "id": "conv_123",
      "title": "Customer inquiry about pricing",
      "snippet": "...asked about <mark>pricing</mark> and <mark>features</mark>...",
      "score": 0.95,
      "created_at": "2024-01-15T00:00:00Z"
    }
  ],
  "meta": {
    "total": 12,
    "took_ms": 45
  }
}
```

## Summaries

### Regenerate Summary

Regenerate AI summary for a conversation.

```http
POST /conversations/{id}/summaries
```

**Request body:**

```json
{
  "language": "en",
  "style": "concise"
}
```

**Response:**

```json
{
  "id": "summary_123",
  "conversation_id": "conv_123",
  "status": "processing",
  "created_at": "2024-01-01T10:00:00Z"
}
```

## Attachments

### List Attachments

Get all attachments for a conversation.

```http
GET /conversations/{id}/attachments
```

### Upload Attachment

Upload a file to a conversation.

```http
POST /conversations/{id}/attachments
```

**Form data:**

```
file: (binary)
filename: document.pdf
```

**Response:**

```json
{
  "id": "att_124",
  "filename": "document.pdf",
  "size": 204800,
  "mime_type": "application/pdf",
  "url": "https://storage.aimychats.com/att_124",
  "created_at": "2024-01-01T10:00:00Z"
}
```

### Delete Attachment

Delete an attachment.

```http
DELETE /attachments/{id}
```

## Account

### Get Account Info

Get current account information.

```http
GET /account
```

**Response:**

```json
{
  "id": "user_123",
  "email": "user@example.com",
  "plan": "professional",
  "storage": {
    "used_mb": 125,
    "limit_mb": 200
  },
  "api_usage": {
    "requests_today": 234,
    "limit_per_day": 5000
  },
  "created_at": "2023-01-01T00:00:00Z"
}
```

### Get Usage Statistics

Get detailed usage statistics.

```http
GET /account/usage
```

**Query parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `from` | string | Start date (ISO 8601) |
| `to` | string | End date (ISO 8601) |

**Response:**

```json
{
  "period": {
    "from": "2024-01-01",
    "to": "2024-01-31"
  },
  "conversations": {
    "total": 45,
    "by_source": {
      "email": 30,
      "api": 15
    }
  },
  "storage": {
    "total_mb": 125,
    "by_type": {
      "conversations": 50,
      "attachments": 75
    }
  },
  "api_requests": {
    "total": 2340,
    "by_endpoint": {
      "/conversations": 1200,
      "/search": 890,
      "/summaries": 250
    }
  }
}
```

## Export

### Create Export

Export conversations in various formats.

```http
POST /exports
```

**Request body:**

```json
{
  "format": "pdf",
  "filters": {
    "date_from": "2024-01-01",
    "date_to": "2024-01-31"
  },
  "options": {
    "include_attachments": true
  }
}
```

**Response:**

```json
{
  "id": "export_123",
  "status": "processing",
  "format": "pdf",
  "created_at": "2024-01-01T10:00:00Z"
}
```

### Get Export Status

Check export status and download when ready.

```http
GET /exports/{id}
```

**Response:**

```json
{
  "id": "export_123",
  "status": "completed",
  "format": "pdf",
  "size_mb": 5.2,
  "download_url": "https://storage.aimychats.com/exports/export_123.pdf",
  "expires_at": "2024-01-08T10:00:00Z",
  "created_at": "2024-01-01T10:00:00Z"
}
```

## Error Responses

### Error Format

All errors follow this format:

```json
{
  "error": {
    "code": "error_code",
    "message": "Human-readable error message",
    "details": {
      // Additional error details
    }
  }
}
```

### Common Error Codes

| Status | Code | Description |
|--------|------|-------------|
| 400 | `bad_request` | Invalid request parameters |
| 401 | `unauthorized` | Missing or invalid API key |
| 403 | `forbidden` | Insufficient permissions |
| 404 | `not_found` | Resource not found |
| 422 | `validation_error` | Request validation failed |
| 429 | `rate_limit_exceeded` | Too many requests |
| 500 | `internal_error` | Server error |
| 503 | `service_unavailable` | Service temporarily unavailable |

### Validation Errors

```json
{
  "error": {
    "code": "validation_error",
    "message": "Validation failed",
    "details": {
      "fields": {
        "title": ["Title is required"],
        "content": ["Content must be less than 10000 characters"]
      }
    }
  }
}
```

## Rate Limits

See [Authentication](/api/authentication#rate-limiting) for rate limit details.

## Pagination

Paginated endpoints return:

```json
{
  "data": [...],
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 100,
    "total_pages": 5
  },
  "links": {
    "first": "https://api.aimychats.com/v1/conversations?page=1",
    "last": "https://api.aimychats.com/v1/conversations?page=5",
    "prev": null,
    "next": "https://api.aimychats.com/v1/conversations?page=2"
  }
}
```

## Changelog

### v1 (Current)

- Initial API release
- Conversations CRUD
- Search functionality
- Summaries
- Exports
- Webhooks

## Support

Questions about the API? [Contact support](mailto:support@email.aimychats.com) or check [Authentication](/api/authentication) and [Webhooks](/api/webhooks).
