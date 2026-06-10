# 📱 Mobile Developer Quick Start — SecureNet SOC

> هذا الملف مخصص لمطور الموبايل — كل اللي محتاجه عشان تبدأ تشتغل على الـ Mobile App.

---

## 1. الأدوات اللي هتحتاجها

| أداة | الغرض |
|---|---|
| **Postman** | تجربة الـ APIs قبل ما تكتب كود |
| **Flutter / React Native** | Framework الموبايل |
| **Android Studio / Xcode** | Emulator + Build |

---

## 2. إعداد الاتصال بالـ Backend

### Base URL
```
Development:  http://<server-ip>:8005
Production:   https://api.yourdomain.com
```

### اختبار الاتصال
```bash
curl http://<server-ip>:8005/health
# Expected: {"status": "healthy", "service": "mobile_gateway"}
```

---

## 3. استيراد Postman Collection

1. افتح Postman
2. اختر **Import**
3. اسحب الملف: `docs/SecureNet_Mobile_API.postman_collection.json`
4. غيّر variable اسمه `base_url` للـ IP بتاع السيرفر
5. جرّب **Login** أول حاجة — الـ tokens بتتحفظ تلقائي

---

## 4. بيانات الدخول (Test Account)

```
Email:    admin@securenet.local
Password: (هيتبعتلك من الـ Backend Team)
```

---

## 5. الـ Authentication Flow (مهم جداً)

```
┌─────────────────────┐
│  POST /v1/mobile/auth │ ← Login → access_token + refresh_token
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  استخدم access_token │ ← كل الـ requests التانية
│  في Header:          │
│  Authorization:      │
│  Bearer <token>      │
└──────────┬──────────┘
           │ لما يرجع 401
           ▼
┌──────────────────────────┐
│ POST /v1/mobile/auth/refresh │ ← أعد التجديد
│ body: { refresh_token }      │
└──────────────────────────┘
```

### قواعد مهمة:
- **Access Token** مدته **30 دقيقة**
- **Refresh Token** بيتستخدم **مرة واحدة بس** — لما تعمل refresh هتاخد واحد جديد
- لو الـ refresh token اتاستخدم مرتين → الاتنين هيتلغوا (أمان)
- خزّن الـ tokens في **Secure Storage** (Keychain / EncryptedSharedPreferences)

---

## 6. شكل الـ Response (ثابت في كل الـ APIs)

### Success:
```json
{
  "success": true,
  "data": { ... },
  "message": "OK"
}
```

### Paginated List:
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

### Error:
```json
{
  "success": false,
  "error": {
    "code": "AUTH_TOKEN_EXPIRED",
    "message": "Token has expired"
  }
}
```

---

## 7. أهم الـ Screens وال APIs بتاعتها

### 🔐 Login Screen
```
POST /v1/mobile/auth
POST /v1/mobile/auth/refresh
```

### 📊 Dashboard Screen
```
GET /v1/mobile/dashboard/summary
```

### 🚨 Alerts List Screen
```
GET /v1/mobile/alerts?per_page=20
GET /v1/mobile/alerts?per_page=20&severity=critical
GET /v1/mobile/alerts?per_page=20&cursor=<meta.cursor>
```

### 📄 Alert Detail Screen
```
GET  /v1/mobile/alerts/{id}
PATCH /v1/mobile/alerts/{id}    ← تحديث الحالة
```

### ⚡ Decision Screen (أهم شاشة)
```
POST /v1/mobile/decision
Body: { "alert_id": "...", "action": "APPROVE" }
Actions: APPROVE | REJECT | ESCALATE
```

### 🛡️ Firewall Screen
```
GET    /v1/mobile/firewall?per_page=20
POST   /v1/mobile/firewall/block
DELETE /v1/mobile/firewall/block/{ip}
```

### 👤 Profile Screen
```
GET  /v1/mobile/users/me
POST /v1/mobile/users/me/password
```

---

## 8. الـ WebSocket (Real-time Alerts)

```dart
// Connection
final ws = WebSocket.connect('ws://<server>:8005/ws?token=$accessToken');

// Receive alerts
ws.listen((message) {
  final data = jsonDecode(message);
  if (data['type'] == 'decision_required') {
    // Show push notification or navigate to decision screen
  }
});

// Heartbeat (every 30 seconds)
Timer.periodic(Duration(seconds: 30), (_) {
  ws.add(jsonEncode({"type": "ping"}));
});
```

---

## 9. Push Notifications (FCM)

بعد ما تعمل setup لـ Firebase:
```
POST /v1/mobile/devices/register
Body: {
  "fcm_token": "firebase-token",
  "device_name": "iPhone 15",
  "platform": "ios"
}
```

---

## 10. Error Handling Strategy

```dart
Future<Response> secureRequest(String path) async {
  final response = await http.get(
    Uri.parse('$baseUrl$path'),
    headers: {'Authorization': 'Bearer $accessToken'},
  );

  switch (response.statusCode) {
    case 200: return response;
    case 401:
      // Try refresh
      final refreshed = await refreshToken();
      if (refreshed) return secureRequest(path); // retry
      else navigateToLogin(); // force re-login
      break;
    case 429:
      // Rate limited — wait and retry
      await Future.delayed(Duration(seconds: 60));
      return secureRequest(path);
    default:
      throw ApiException(response.body);
  }
}
```

---

## 📚 مراجع إضافية

| ملف | وصف |
|---|---|
| `docs/mobile_integration_guide.md` | دليل تفصيلي لكل الـ APIs |
| `docs/websocket_protocol.md` | بروتوكول الـ WebSocket كامل |
| `http://<server>:8005/docs` | Swagger UI — تجربة APIs من البراوزر |
| `http://<server>:8005/redoc` | ReDoc — API reference منسق |
| `docs/SecureNet_Mobile_API.postman_collection.json` | Postman Collection جاهزة |
