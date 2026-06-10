# SecureNet SOC — Mobile Integration Guide

## Overview

This guide covers everything needed to integrate a mobile client (Flutter, React Native, or native) with the SecureNet Mobile Gateway.

**Base URL:** `http://16.171.61.103:8005` (dev) or `https://api.yourdomain.com/mobile` (prod)  
**API Version:** `v1`  
**Auth:** JWT Bearer tokens  
**Response format:** Standardized JSON envelope

---

## 1. Authentication

### Login

```http
POST /v1/mobile/auth
Content-Type: application/json

{
  "email": "analyst@securenet.local",
  "password": "your-password"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbG...",
    "refresh_token": "eyJhbG...",
    "token_type": "bearer",
    "expires_in": 1800,
    "role": "analyst"
  }
}
```

**Token Storage:**
- Store `access_token` in secure storage (iOS Keychain / Android EncryptedSharedPreferences)
- Store `refresh_token` separately — it is single-use
- Schedule refresh at `expires_in - 60` seconds

### Token Refresh

```http
POST /v1/mobile/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbG..."
}
```

**Response:** Same structure as login. The old refresh token is **invalidated**.

### Logout

```http
POST /v1/mobile/auth/logout
Authorization: Bearer <access_token>
```

**Response (200):**
```json
{
  "success": true,
  "data": null,
  "message": "Logged out"
}
```

### Error Handling

| Status | Code | Description |
|---|---|---|
| 401 | `AUTH_INVALID` | Invalid credentials |
| 401 | `AUTH_TOKEN_EXPIRED` | Access token expired — refresh |
| 429 | `RATE_LIMITED` | Too many attempts (wait 60s) |
| 429 | `ACCOUNT_LOCKED` | 5+ failures — locked 15 min |

---

## 2. Standard Response Envelope

All responses follow this structure:

### Success
```json
{
  "success": true,
  "data": { ... },
  "message": "OK"
}
```

### Paginated
```json
{
  "success": true,
  "data": [ ... ],
  "meta": {
    "per_page": 20,
    "has_next": true,
    "cursor": "2026-05-16T02:30:00"
  }
}
```

### Error
```json
{
  "success": false,
  "error": {
    "code": "AUTH_TOKEN_EXPIRED",
    "message": "Token has expired",
    "details": null
  }
}
```

---

## 3. Alerts

### List Alerts (Paginated)

```http
GET /v1/mobile/alerts?per_page=20&severity=critical&status=new
Authorization: Bearer <token>
```

**Query Parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `per_page` | int | 20 | Items per page (max 100) |
| `cursor` | string | null | ISO timestamp for next page |
| `severity` | string | null | Filter: `low`, `medium`, `high`, `critical` |
| `status` | string | null | Filter: `new`, `acknowledged`, `resolved`, `false_positive` |

**Pagination:** Use `meta.cursor` from the response as the `cursor` param for the next page. Stop when `meta.has_next` is `false`.

### Get Alert Detail

```http
GET /v1/mobile/alerts/{alert_id}
Authorization: Bearer <token>
```

### Update Alert Status

```http
PATCH /v1/mobile/alerts/{alert_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "status": "acknowledged",
  "analyst_notes": "Investigating source network segment"
}
```

**Allowed roles:** `admin`, `analyst`

---

## 4. Decision Flow

When a critical/high alert is routed to mobile, the SOC analyst must act:

### Submit Decision

```http
POST /v1/mobile/decision
Authorization: Bearer <token>
Content-Type: application/json

{
  "alert_id": "abc-123",
  "action": "APPROVE"
}
```

**Actions:** `APPROVE` (block IP), `REJECT` (ignore), `ESCALATE` (flag for review)

### Decision History

```http
GET /v1/mobile/decisions?per_page=20
Authorization: Bearer <token>
```

---

## 5. Firewall Management

### List Blocked IPs

```http
GET /v1/mobile/firewall?per_page=20
Authorization: Bearer <token>
```

### Block IP

```http
POST /v1/mobile/firewall/block
Authorization: Bearer <token>
Content-Type: application/json

{
  "ip_address": "192.168.1.100",
  "reason": "Manual block after investigation"
}
```

**Allowed roles:** `admin`, `analyst`

### Unblock IP

```http
DELETE /v1/mobile/firewall/block/192.168.1.100
Authorization: Bearer <token>
```

---

## 6. Dashboard Summary

### Get Aggregated Statistics

```http
GET /v1/mobile/dashboard/summary
Authorization: Bearer <token>
```

**Response:**
```json
{
  "success": true,
  "data": {
    "alerts_by_severity": {
      "critical": 5, "high": 12, "medium": 34, "low": 89
    },
    "alerts_by_status": {
      "new": 15, "acknowledged": 8, "resolved": 102
    },
    "total_blocked_ips": 23,
    "recent_blocks_24h": 7,
    "decisions_today": 12
  }
}
```

---

## 7. User Profile

### Get Profile

```http
GET /v1/mobile/users/me
Authorization: Bearer <token>
```

### Change Password

```http
POST /v1/mobile/users/me/password
Authorization: Bearer <token>
Content-Type: application/json

{
  "current_password": "old-password",
  "new_password": "new-strong-password"
}
```

---

## 8. Push Notifications (FCM)

### Register Device

```http
POST /v1/mobile/devices/register
Authorization: Bearer <token>
Content-Type: application/json

{
  "fcm_token": "firebase-token-here",
  "device_name": "iPhone 15 Pro",
  "platform": "ios"
}
```

---

## 9. WebSocket Connection

### Connect

```
ws://16.171.61.103:8005/ws/mobile?token=<access_token>
```

### Messages (Server → Client)

```json
{
  "type": "new_alert",
  "data": {
    "alert_id": "abc-123",
    "src_ip": "192.168.1.100",
    "attack_type": "DDoS",
    "severity": "critical"
  }
}
```

### Heartbeat

Send `{"type": "ping"}` every 30 seconds. Server responds with `{"type": "pong"}`.

If no pong within 10 seconds, reconnect with exponential backoff (1s → 2s → 4s → ... → 30s max).

---

## 10. Error Handling Best Practices

```
401 Unauthorized → Attempt token refresh → If refresh fails → Force re-login
429 Rate Limited  → Wait `Retry-After` seconds → Retry
500 Server Error  → Retry with exponential backoff (max 3 attempts)
Network Error     → Queue locally → Sync when connection restored
```

### Retry Strategy (Dart/Flutter Example)

```dart
Future<Response> apiCall(String path) async {
  for (int attempt = 0; attempt < 3; attempt++) {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl$path'),
        headers: {'Authorization': 'Bearer $accessToken'},
      );

      if (response.statusCode == 401) {
        await refreshToken();
        continue;
      }

      return response;
    } catch (e) {
      if (attempt == 2) rethrow;
      await Future.delayed(Duration(seconds: 1 << attempt));
    }
  }
  throw Exception('API call failed after 3 attempts');
}
```
