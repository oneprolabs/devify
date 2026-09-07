# Authentication

## API Authentication

AImyChats API uses API keys for authentication. All API requests must include your API key in the Authorization header.

## Getting Your API Key

1. Log in to your AImyChats account
2. Navigate to Settings → API
3. Click "Generate New API Key"
4. Copy and securely store your key

::: warning
Keep your API keys secure! Never share them publicly or commit them to version control.
:::

## Authentication Methods

### API Key Authentication

Include your API key in the `Authorization` header:

```bash
curl -X GET https://api.aimychats.com/v1/conversations \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json"
```

### OAuth 2.0 (Pro Plan)

Pro plan customers can use OAuth 2.0 for server-to-server authentication.

**Authorization endpoint:**
```
https://api.aimychats.com/oauth/authorize
```

**Token endpoint:**
```
https://api.aimychats.com/oauth/token
```

**Example OAuth flow:**

```javascript
// Step 1: Get authorization code
const authUrl = 'https://api.aimychats.com/oauth/authorize?' +
  'client_id=YOUR_CLIENT_ID&' +
  'redirect_uri=YOUR_REDIRECT_URI&' +
  'response_type=code&' +
  'scope=read write'

// Step 2: Exchange code for token
const response = await fetch('https://api.aimychats.com/oauth/token', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/x-www-form-urlencoded'
  },
  body: new URLSearchParams({
    grant_type: 'authorization_code',
    code: 'AUTHORIZATION_CODE',
    client_id: 'YOUR_CLIENT_ID',
    client_secret: 'YOUR_CLIENT_SECRET',
    redirect_uri: 'YOUR_REDIRECT_URI'
  })
})

const { access_token, refresh_token } = await response.json()
```

## Making Authenticated Requests

### JavaScript/Node.js

```javascript
const API_KEY = 'your_api_key_here'
const BASE_URL = 'https://api.aimychats.com/v1'

async function getConversations() {
  const response = await fetch(`${BASE_URL}/conversations`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${API_KEY}`,
      'Content-Type': 'application/json'
    }
  })

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }

  return await response.json()
}
```

### Python

```python
import requests

API_KEY = 'your_api_key_here'
BASE_URL = 'https://api.aimychats.com/v1'

headers = {
    'Authorization': f'Bearer {API_KEY}',
    'Content-Type': 'application/json'
}

response = requests.get(f'{BASE_URL}/conversations', headers=headers)
response.raise_for_status()
data = response.json()
```

### cURL

```bash
curl -X GET "https://api.aimychats.com/v1/conversations" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json"
```

## API Key Scopes

API keys can have different permission scopes:

| Scope | Description |
|-------|-------------|
| `read` | Read conversations and summaries |
| `write` | Create and update conversations |
| `delete` | Delete conversations |
| `admin` | Full account access |

::: tip
Create separate API keys with limited scopes for different use cases to enhance security.
:::

## Rate Limiting

API requests are rate-limited based on your subscription plan:

| Plan | Rate Limit | Burst Limit |
|------|------------|-------------|
| Free | 100/hour | 10/minute |
| Starter | 500/hour | 50/minute |
| Standard | 2,000/hour | 100/minute |
| Pro | 10,000/hour | 500/minute |

### Rate Limit Headers

API responses include rate limit information:

```http
X-RateLimit-Limit: 5000
X-RateLimit-Remaining: 4999
X-RateLimit-Reset: 1609459200
```

### Handling Rate Limits

When you exceed the rate limit, you'll receive a `429 Too Many Requests` response:

```json
{
  "error": {
    "code": "rate_limit_exceeded",
    "message": "Rate limit exceeded. Please try again later.",
    "retry_after": 3600
  }
}
```

**Recommended approach:**

```javascript
async function makeRequestWithRetry(url, options, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    const response = await fetch(url, options)

    if (response.status === 429) {
      const retryAfter = response.headers.get('Retry-After') || 60
      await new Promise(resolve => setTimeout(resolve, retryAfter * 1000))
      continue
    }

    return response
  }

  throw new Error('Max retries exceeded')
}
```

## Error Responses

### Authentication Errors

**401 Unauthorized - Missing or invalid API key:**

```json
{
  "error": {
    "code": "unauthorized",
    "message": "Invalid or missing API key"
  }
}
```

**403 Forbidden - Insufficient permissions:**

```json
{
  "error": {
    "code": "forbidden",
    "message": "Insufficient permissions for this operation"
  }
}
```

## Security Best Practices

### Storing API Keys

- Never hardcode API keys in source code
- Use environment variables or secure vaults
- Rotate API keys regularly
- Delete unused API keys

**Example with environment variables:**

```javascript
// .env file (never commit this)
DEVIFY_API_KEY=your_api_key_here

// In your code
const API_KEY = process.env.DEVIFY_API_KEY
```

### HTTPS Only

All API requests must use HTTPS. HTTP requests will be rejected:

```json
{
  "error": {
    "code": "insecure_connection",
    "message": "HTTPS required for API requests"
  }
}
```

### IP Whitelisting (Pro Plan)

Pro plan customers can restrict API access to specific IP addresses:

1. Go to Settings → API → Security
2. Enable IP whitelisting
3. Add allowed IP addresses or CIDR ranges

## Testing Authentication

Test your API key with this simple request:

```bash
curl -X GET "https://api.aimychats.com/v1/auth/test" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Success response:**

```json
{
  "authenticated": true,
  "user": {
    "id": "user_123",
    "email": "user@example.com"
  },
  "scopes": ["read", "write"],
  "rate_limit": {
    "limit": 5000,
    "remaining": 4999,
    "reset": 1609459200
  }
}
```

## Next Steps

- [API Reference](/api/reference) - Complete API endpoint documentation
- [Webhooks](/api/webhooks) - Set up real-time notifications
- [Code Examples](#) - More integration examples

## Support

Having trouble with authentication? [Contact support](mailto:support@email.aimychats.com) or check our [FAQ](/en/faq).
