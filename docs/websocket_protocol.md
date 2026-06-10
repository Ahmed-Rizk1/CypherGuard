# SecureNet SOC — WebSocket Protocol

## Overview

Both the API Gateway and Mobile Gateway expose WebSocket endpoints for real-time telemetry and alert notifications.

## Endpoints

| Gateway | Endpoint | Auth |
|---|---|---|
| API Gateway | `ws://localhost:8000/ws?token=<jwt>` | JWT query param |
| Mobile Gateway | `ws://localhost:8005/ws?token=<jwt>` | JWT query param |

## Connection Lifecycle

```
Client                          Server
  │                                │
  ├──── WS Connect (?token=JWT) ──►│
  │                                ├── Validate JWT
  │◄── Connection Accepted ────────┤
  │                                │
  │◄── telemetry_update (1/sec) ───┤  (API Gateway)
  │◄── new_alert ──────────────────┤  (when alert generated)
  │◄── decision_required ──────────┤  (Mobile Gateway, critical alerts)
  │                                │
  ├──── {"type": "ping"} ─────────►│
  │◄── {"type": "pong"} ───────────┤
  │                                │
  ├──── Close ─────────────────────►│
  │◄── Close ACK ──────────────────┤
```

## Message Types

### Server → Client

#### `telemetry_update` (API Gateway, every 1 second)
```json
{
  "type": "telemetry_update",
  "data": {
    "packets_per_sec": 1250,
    "bytes_per_sec": 512000,
    "active_connections": 42,
    "blocked_ips": ["192.168.1.100", "10.0.0.50"],
    "recent_alerts": [
      {
        "timestamp": "2026-05-16T03:45:00Z",
        "alert_id": "abc-123",
        "src_ip": "192.168.1.100",
        "attack_type": "DDoS Volumetric Flood",
        "severity": "critical",
        "explanation": "High packet rate detected."
      }
    ],
    "alert_hash": "a1b2c3d4",
    "blocklist_hash": "e5f6g7h8"
  }
}
```

#### `new_alert` (Both gateways)
```json
{
  "type": "new_alert",
  "data": {
    "alert_id": "abc-123",
    "src_ip": "192.168.1.100",
    "attack_type": "DDoS",
    "severity": "critical",
    "confidence": 0.95
  }
}
```

#### `decision_required` (Mobile Gateway)
```json
{
  "type": "decision_required",
  "data": {
    "alert_id": "abc-123",
    "src_ip": "192.168.1.100",
    "reason": "DDoS Volumetric Flood - critical",
    "severity": "critical",
    "confidence": "0.9500",
    "timeout_seconds": 60
  }
}
```

### Client → Server

#### `ping` (Heartbeat)
```json
{"type": "ping"}
```

**Response:** `{"type": "pong"}`

**Interval:** Send every 30 seconds. If no pong within 10 seconds, consider the connection dead.

## Reconnection Strategy

```
Attempt 1: Wait 1 second
Attempt 2: Wait 2 seconds
Attempt 3: Wait 4 seconds
Attempt 4: Wait 8 seconds
Attempt 5: Wait 16 seconds
Attempt 6+: Wait 30 seconds (max)
```

On reconnection:
1. Re-authenticate with a fresh token (refresh if needed)
2. Fetch latest alerts via REST to catch up on missed events
3. Resume WebSocket subscription

## Token Expiry Handling

The Mobile Gateway monitors token expiry during WebSocket sessions:
- When token has < 5 minutes remaining, the server sends a warning
- Client should refresh token and reconnect
- If token expires, the server closes the connection with code 4001

## Error Codes

| Code | Meaning |
|---|---|
| 1000 | Normal close |
| 1008 | Policy violation (invalid token) |
| 4001 | Token expired |
| 4002 | Token revoked |
| 4003 | Rate limited |
