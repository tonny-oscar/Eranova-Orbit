# Orbit product integration contract

Your live products (CRM, ShulePoa, HostPilot and others) stay in their own repositories and
deployments. To appear in Orbit, each one exposes a small read-only API. Orbit polls it on a
schedule and stores only **aggregate numbers**, never copies of the product's customer records.

## 1. Credentials

1. In the product, issue a read-only API key for Orbit.
2. On the Orbit API server (Render → Environment), add it as an environment variable whose name
   starts with `INTEGRATION_`, for example `INTEGRATION_CRM_API_KEY`.
3. In Orbit → Integrations → *Connect a system*, choose **Eranova product API** and enter the
   variable **name** (not the key) as the credential variable.

Orbit never stores secret values in the database, and only variables named `INTEGRATION_*` can
be referenced, so a connection cannot read other server secrets such as `SECRET_KEY`.

Every request carries `Authorization: Bearer <key>`.

## 2. Health — `GET /orbit/health`

```json
{ "status": "ok", "version": "3.4.1" }
```

`status` of `ok`, `healthy` or `pass` counts as healthy. Any other value, a non-2xx response,
a timeout or a TLS error is reported as a failed check. The path can be changed per connection.

## 3. Metrics — `GET /orbit/metrics`

```json
{
  "period": "2026-11-12",
  "as_of": "2026-11-12T09:00:00Z",
  "metrics": {
    "active_customers": 42,
    "mrr_kes": 125000,
    "open_tickets": 7
  }
}
```

- Only numeric values are kept (booleans and strings are dropped); at most 50 metrics.
- Use clear snake_case names: Orbit shows `active_customers` as "active customers".
- Report real figures only. Omit a metric rather than send a placeholder.
- `period` identifies the reporting period. Re-sending the same period updates it in place.

## 4. Webhooks (optional) — `POST <Orbit webhook URL>`

Each connection shows its webhook URL in Orbit. To push events instead of waiting for the next
poll, add a second variable (for example `INTEGRATION_CRM_WEBHOOK_SECRET`), reference it as the
webhook signing variable, and sign each delivery:

| Header              | Value                                                        |
| ------------------- | ------------------------------------------------------------ |
| `X-Orbit-Timestamp` | Unix seconds when sent                                       |
| `X-Orbit-Signature` | hex HMAC-SHA256 of `"<timestamp>." + raw body` with secret   |
| `X-Orbit-Delivery`  | Unique id per delivery (used to drop duplicates)             |

Deliveries older than 5 minutes, unsigned, or with a wrong signature are rejected with `403`
and recorded in the audit log. Duplicate delivery ids return `{"status": "duplicate"}`.

Example (Node.js):

```js
const ts = Math.floor(Date.now() / 1000).toString()
const body = JSON.stringify({ type: 'customer.created', id: crypto.randomUUID() })
const signature = crypto.createHmac('sha256', secret).update(`${ts}.${body}`).digest('hex')
await fetch(webhookUrl, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Orbit-Timestamp': ts,
    'X-Orbit-Signature': signature,
    'X-Orbit-Delivery': JSON.parse(body).id,
  },
  body,
})
```

## 5. Other providers

| Provider       | What Orbit reads                                   | Credential variable holds          |
| -------------- | -------------------------------------------------- | ---------------------------------- |
| GitHub         | Repository summary, open pull requests, PR webhooks | Fine-grained read-only token       |
| Vercel         | Recent deployments and their state                  | Vercel access token                |
| Google Analytics 4 | Daily users, sessions, page views, conversions | Service-account JSON key           |
| Uptime monitor | Status code, latency, TLS certificate expiry        | Nothing                            |

GitHub pull-request webhooks add **evidence** to Orbit tasks that link to the PR. They never
change a task's status; a reviewer still approves the work.

## 6. Network safety

Orbit refuses to call private, loopback or link-local addresses and requires HTTPS outside local
development, so a misconfigured connection cannot be used to reach internal infrastructure.
