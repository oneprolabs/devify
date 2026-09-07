# Webhooks

## Real-time Event Notifications

Webhooks allow you to receive real-time notifications when events occur in your AImyChats account. Instead of polling the API, AImyChats will send HTTP POST requests to your specified endpoint.

## Setting Up Webhooks

### Via Dashboard

1. Log in to your AImyChats account
2. Navigate to Settings → Webhooks
3. Click "Add Webhook"
4. Enter your endpoint URL
5. Select events to subscribe to
6. Save and test

### Via API

```javascript
POST /v1/webhooks

{
  "url": "https://your-app.com/webhooks/devify",
  "events": ["conversation.created", "summary.generated"],
  "description": "Production webhook",
  "active": true
}
```

**Response:**

```json
{
  "id": "webhook_123",
  "url": "https://your-app.com/webhooks/devify",
  "events": ["conversation.created", "summary.generated"],
  "secret": "whsec_abc123...",
  "active": true,
  "created_at": "2024-01-01T00:00:00Z"
}
```

::: warning
Save the `secret` value! You'll need it to verify webhook signatures.
:::

## Available Events

### Conversation Events

| Event | Description |
|-------|-------------|
| `conversation.created` | New conversation created |
| `conversation.updated` | Conversation updated |
| `conversation.deleted` | Conversation deleted |

### Summary Events

| Event | Description |
|-------|-------------|
| `summary.generated` | AI summary completed |
| `summary.failed` | AI summary generation failed |

### Storage Events

| Event | Description |
|-------|-------------|
| `storage.limit_reached` | Storage quota 80% full |
| `storage.limit_exceeded` | Storage quota exceeded |

### Account Events

| Event | Description |
|-------|-------------|
| `subscription.updated` | Subscription plan changed |
| `subscription.cancelled` | Subscription cancelled |
| `api_key.created` | New API key created |
| `api_key.revoked` | API key revoked |

## Webhook Payload

### Structure

All webhook payloads follow this structure:

```json
{
  "id": "evt_123",
  "type": "conversation.created",
  "created_at": "2024-01-01T00:00:00Z",
  "data": {
    // Event-specific data
  }
}
```

### Example Payloads

**conversation.created:**

```json
{
  "id": "evt_abc123",
  "type": "conversation.created",
  "created_at": "2024-01-01T00:00:00Z",
  "data": {
    "conversation": {
      "id": "conv_123",
      "title": "Customer Inquiry",
      "source": "email",
      "created_at": "2024-01-01T00:00:00Z",
      "summary": null,
      "status": "processing"
    }
  }
}
```

**summary.generated:**

```json
{
  "id": "evt_def456",
  "type": "summary.generated",
  "created_at": "2024-01-01T00:05:00Z",
  "data": {
    "conversation_id": "conv_123",
    "summary": {
      "title": "Product inquiry about features",
      "content": "Customer asked about pricing and features...",
      "sentiment": "positive",
      "topics": ["pricing", "features"],
      "action_items": ["Send pricing sheet", "Schedule demo"]
    }
  }
}
```

**storage.limit_reached:**

```json
{
  "id": "evt_ghi789",
  "type": "storage.limit_reached",
  "created_at": "2024-01-01T10:00:00Z",
  "data": {
    "usage": {
      "current_mb": 160,
      "limit_mb": 200,
      "percentage": 80
    },
    "recommendation": "Consider upgrading to a higher plan"
  }
}
```

## Webhook Security

### Signature Verification

All webhooks include a signature in the `X-AImyChats-Signature` header. Verify this signature to ensure the webhook is from AImyChats.

**Signature format:**

```
t=1609459200,v1=5257a869e7ecebeda32affa62cdca3fa51cad7e77a0e56ff536d0ce8e108d8bd
```

**Verification steps:**

1. Extract timestamp `t` and signature `v1`
2. Construct signed payload: `{timestamp}.{raw_body}`
3. Compute HMAC SHA256 using your webhook secret
4. Compare computed signature with `v1`

**Node.js example:**

```javascript
const crypto = require('crypto')

function verifyWebhook(payload, signature, secret) {
  const parts = signature.split(',')
  const timestamp = parts[0].split('=')[1]
  const expectedSig = parts[1].split('=')[1]

  const signedPayload = `${timestamp}.${payload}`
  const computedSig = crypto
    .createHmac('sha256', secret)
    .update(signedPayload)
    .digest('hex')

  return crypto.timingSafeEqual(
    Buffer.from(expectedSig),
    Buffer.from(computedSig)
  )
}

// Express.js middleware
app.post('/webhooks/aimychats', (req, res) => {
  const signature = req.headers['x-aimychats-signature']
  const payload = JSON.stringify(req.body)
  const secret = process.env.WEBHOOK_SECRET

  if (!verifyWebhook(payload, signature, secret)) {
    return res.status(401).send('Invalid signature')
  }

  // Process webhook
  const event = req.body
  console.log('Received event:', event.type)

  res.status(200).send('OK')
})
```

**Python example:**

```python
import hmac
import hashlib
import time

def verify_webhook(payload, signature, secret):
    parts = signature.split(',')
    timestamp = parts[0].split('=')[1]
    expected_sig = parts[1].split('=')[1]

    signed_payload = f"{timestamp}.{payload}"
    computed_sig = hmac.new(
        secret.encode(),
        signed_payload.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_sig, computed_sig)

# Flask example
@app.route('/webhooks/aimychats', methods=['POST'])
def handle_webhook():
    signature = request.headers.get('X-AImyChats-Signature')
    payload = request.get_data(as_text=True)
    secret = os.environ['WEBHOOK_SECRET']

    if not verify_webhook(payload, signature, secret):
        return 'Invalid signature', 401

    event = request.json
    print(f"Received event: {event['type']}")

    return 'OK', 200
```

### Replay Attack Prevention

Check the timestamp in the signature to prevent replay attacks:

```javascript
function isRecentWebhook(signature, toleranceSeconds = 300) {
  const timestamp = parseInt(signature.split(',')[0].split('=')[1])
  const now = Math.floor(Date.now() / 1000)
  return Math.abs(now - timestamp) <= toleranceSeconds
}
```

## Handling Webhooks

### Best Practices

1. **Respond quickly**: Return `200 OK` within 5 seconds
2. **Process asynchronously**: Queue webhook for background processing
3. **Handle duplicates**: Webhooks may be sent multiple times
4. **Log everything**: Keep detailed logs for debugging

**Example with queue:**

```javascript
const queue = require('bull')
const webhookQueue = new queue('webhooks')

app.post('/webhooks/devify', async (req, res) => {
  // Verify signature
  if (!verifyWebhook(...)) {
    return res.status(401).send('Invalid signature')
  }

  // Queue for processing
  await webhookQueue.add(req.body)

  // Respond immediately
  res.status(200).send('OK')
})

// Process in background
webhookQueue.process(async (job) => {
  const event = job.data

  switch (event.type) {
    case 'conversation.created':
      await handleNewConversation(event.data)
      break
    case 'summary.generated':
      await handleNewSummary(event.data)
      break
    default:
      console.log(`Unhandled event: ${event.type}`)
  }
})
```

### Idempotency

Use the event `id` to handle duplicate webhooks:

```javascript
const processedEvents = new Set()

async function processWebhook(event) {
  if (processedEvents.has(event.id)) {
    console.log('Duplicate event, skipping')
    return
  }

  processedEvents.add(event.id)

  // Process event
  await handleEvent(event)
}
```

## Retry Logic

### Automatic Retries

If your endpoint fails to respond with `200 OK`, Devify will retry:

- First retry: After 1 minute
- Second retry: After 5 minutes
- Third retry: After 30 minutes
- Fourth retry: After 2 hours
- Fifth retry: After 6 hours

After 5 failed attempts, the webhook is marked as failed.

### Manual Retry

Retry failed webhooks via dashboard or API:

```javascript
POST /v1/webhooks/{webhook_id}/events/{event_id}/retry
```

## Testing Webhooks

### Test Endpoint

Send a test webhook to verify your setup:

```javascript
POST /v1/webhooks/{webhook_id}/test

{
  "event_type": "conversation.created"
}
```

### Local Testing

Use tools like ngrok for local development:

```bash
# Start ngrok
ngrok http 3000

# Use the ngrok URL as your webhook URL
https://abc123.ngrok.io/webhooks/devify
```

### Webhook Logs

View webhook delivery logs in the dashboard:
- Request payload
- Response status
- Response time
- Error messages

## Managing Webhooks

### List Webhooks

```javascript
GET /v1/webhooks
```

### Update Webhook

```javascript
PATCH /v1/webhooks/{webhook_id}

{
  "events": ["conversation.created"],
  "active": false
}
```

### Delete Webhook

```javascript
DELETE /v1/webhooks/{webhook_id}
```

## Troubleshooting

### Webhook Not Received

1. Check webhook is active
2. Verify endpoint URL is correct
3. Check firewall settings
4. Review webhook logs in dashboard

### Signature Verification Fails

1. Use correct webhook secret
2. Don't modify request body before verification
3. Check timestamp tolerance

### Timeout Issues

1. Return `200 OK` immediately
2. Process webhooks asynchronously
3. Increase server timeout settings

## Rate Limits

Webhook deliveries don't count towards your API rate limits. However, we limit:

- Maximum 10 webhooks per account
- Maximum 1000 events per hour per webhook

## Examples

### Slack Notification

```javascript
async function sendSlackNotification(event) {
  if (event.type === 'summary.generated') {
    await fetch(SLACK_WEBHOOK_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: `New summary: ${event.data.summary.title}`,
        blocks: [
          {
            type: 'section',
            text: {
              type: 'mrkdwn',
              text: `*${event.data.summary.title}*\n${event.data.summary.content}`
            }
          }
        ]
      })
    })
  }
}
```

### Database Sync

```javascript
async function syncToDatabase(event) {
  if (event.type === 'conversation.created') {
    await db.conversations.insert({
      devify_id: event.data.conversation.id,
      title: event.data.conversation.title,
      created_at: event.data.conversation.created_at
    })
  }
}
```

## Next Steps

- [Authentication](/api/authentication) - Set up API authentication
- [API Reference](/api/reference) - Complete API documentation
- [Code Examples](#) - More integration examples

## Support

Need help with webhooks? [Contact support](mailto:support@email.aimychats.com) or check our [FAQ](/en/faq).
