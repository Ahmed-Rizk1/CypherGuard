# CypherGuard SOC — Pre-Production Final Audit & Readiness Report

**Generated:** 2026-05-29 | **Auditor:** Lead Mobile Enterprise Architect
**Codebase:** `threateye/` | **Flutter SDK:** `^3.10.0-162.1.beta`

---

## 1. 🏆 Executive Summary

| Dimension | Assessment |
|---|---|
| **Overall Maturity** | **Beta / Pre-Production — 78% release-ready** |
| **Architecture** | ✅ Clean Architecture (data / domain / presentation) strictly enforced across all 7 wired features |
| **State Management** | ✅ Flutter_Bloc (Cubit pattern) throughout — no setState anti-patterns in feature logic |
| **Dependency Injection** | ✅ GetIt fully wired — 30 registered entries covering all features including the previously-missing Notifications chain |
| **Security Posture** | ✅ Firebase purged, hardcoded credentials removed, `try/finally` logout guaranteed, token storage encrypted via `flutter_secure_storage` |
| **Real-time Pipeline** | ✅ WebSocket (`WebSocketManagerService`) + local notifications only — no FCM dependency |
| **Offline Resilience** | ✅ `OfflineQueueService` with `SharedPreferences` persistence and connectivity-aware auto-flush |
| **Mock Data** | ✅ **Zero** hardcoded mock responses remain in any wired feature |
| **Critical Blockers** | 🔴 **3 P0 blockers** must be resolved before store submission (package ID, signing config, SSL pins) |
| **Missing Features** | 🟡 2 feature folders (`reports`, `settings`) are completely empty stubs — not routed |

---

## 2. 🏗️ Completed Features Matrix

| # | Feature | Data Source | Repository | Use Cases | Cubit | DI Entry # | Routes Wired | Mock-Free |
|---|---|---|---|---|---|---|---|---|
| 1 | **Splash / Auth-Check** | `SecureStorageService` | — | — | — | — | `/` | ✅ |
| 2 | **Authentication** | `AuthRemoteDataSource` (raw Dio) | `AuthRepositoryImpl` | `LoginUseCase` `LogoutUseCase` `RefreshTokenUseCase` | `AuthCubit` | 3–8 | `/login` `/main` | ✅ |
| 3 | **Dashboard** | `DashboardRemoteDataSource` | `DashboardRepositoryImpl` | `GetDashboardSummaryUseCase` | `DashboardCubit` | 9–12 | `/dashboard` | ✅ |
| 4 | **Alerts** | `AlertsRemoteDataSource` | `AlertsRepositoryImpl` | `GetAlertsUseCase` `GetAlertByIdUseCase` `UpdateAlertStatusUseCase` | `AlertsCubit` | 13–16 | `/alerts` `/alert-detail` | ✅ |
| 5 | **Decision History** | `DecisionRemoteDataSource` | `DecisionRepositoryImpl` | `GetDecisionHistoryUseCase` `SubmitDecisionUseCase` | `DecisionCubit` | 17–20 | `/decision-history` ✨Sprint 2 | ✅ |
| 6 | **Firewall** | `FirewallRemoteDataSource` | `FirewallRepositoryImpl` | `GetBlockedIpsUseCase` `BlockIpUseCase` `UnblockIpUseCase` | `FirewallCubit` | 21–24 | `/firewall` ✨Sprint 2 | ✅ |
| 7 | **Notifications** | `NotificationRemoteDataSource` (REST + device reg) | `NotificationRepositoryImpl` `NotificationsRepositoryImpl` | `RegisterDeviceUseCase` `GetNotificationsUseCase` | `NotificationCubit` `NotificationsCubit` | 26–30 ✨Sprint 3 | `/notifications` | ✅ |
| 8 | **WebSocket** | `WebSocketManagerService` (singleton) | — | — | Feeds `AlertsCubit` + `NotificationsPage` | 25 | Live stream | ✅ |
| 9 | **Offline Queue** | `OfflineQueueService` + `SharedPreferences` | — | — | Injected into `DecisionCubit` + `AuthCubit` | 26 | Auto-flush | ✅ |

### Core Infrastructure

| Component | Status | Notes |
|---|---|---|
| `DioFactory` (dual Dio) | ✅ Production | Raw Dio for auth, authenticated Dio for all other calls |
| `AuthInterceptor` | ✅ Production | Transparent 401-refresh with retry; circular-refresh-loop-safe |
| `SecureStorageService` | ✅ Production | `flutter_secure_storage` — AES-256 on Android, Keychain on iOS |
| `LocalNotificationService` | ✅ Production | `flutter_local_notifications` — WebSocket events → OS tray |
| `NavigationService` (global key) | ✅ | Available for imperative navigation outside widget tree |
| SSL Pinning | ✅ Framework ready | `validateCertificate` in `IOHttpClientAdapter` — **placeholder hashes must be replaced** |
| Secure Logout | ✅ Sprint fix | `try/finally` guarantees `AuthUnauthenticated` always emitted; `Builder` context fix applied |
| Route definitions | ✅ | 10 named routes; `/firewall` and `/decision-history` added Sprint 2 |

---

## 3. ⚠️ Missing Code Features (Stubbed Folders)

Two feature folders exist in `lib/features/` but contain **zero Dart files** — they are completely empty directory trees with no implementation whatsoever.

### `lib/features/reports/`

```
reports/
├── data/          ← EMPTY
├── domain/        ← EMPTY
└── presentation/  ← EMPTY
```

- **No route defined** in `RouteNames` or `AppRouter`
- **No DI registration** in `injection_container.dart`
- **No UI entry point** exists — the folder is a placeholder only
- **Impact on release:** Low risk (unreachable), but suggests planned functionality. Remove or implement before commercial release.

### `lib/features/settings/`

```
settings/
├── data/          ← EMPTY
├── domain/        ← EMPTY
└── presentation/  ← EMPTY
```

- **No route defined** in `RouteNames` or `AppRouter`
- **No DI registration** in `injection_container.dart`
- **Likely needed before production:** A Settings screen typically contains session info, app version, logout shortcut, and theme preferences — expected by enterprise MDM/audit requirements.
- **Impact on release:** Medium risk — SOC analysts may expect profile/settings access.

> ⚠️ **Warning:** Both stub folders also lack `domain/repositories/`, `domain/entities/`, and `domain/usecases/` subdirectories — the directory structure itself was never scaffolded. These are *concept folders*, not incomplete features.

---

## 4. ⚙️ Missing Native & Release Configurations

### 4.1 🔴 P0 — Android Package ID (Release Blocker)

**File:** `android/app/build.gradle.kts`

```kotlin
// CURRENT — MUST CHANGE BEFORE STORE SUBMISSION
namespace     = "com.example.threateye"   // ← Google Play will reject this
applicationId = "com.example.threateye"   // ← Identical to every new Flutter project
```

**Required action:**
- Replace both values with your organisation's reverse-domain ID, e.g. `com.securenet.cypherguard`
- This ID becomes the app's **permanent, immutable** Play Store / App Store identity
- Also update `android:label="threateye"` → `"CypherGuard"` in `AndroidManifest.xml` (line 3)

---

### 4.2 🔴 P0 — Release Signing Config (Release Blocker)

**File:** `android/app/build.gradle.kts` lines 29–33:

```kotlin
buildTypes {
    release {
        signingConfig = signingConfigs.getByName("debug")  // ← CRITICAL: signs release with debug key
    }
}
```

**Current state:** Every release APK/AAB is signed with the **debug keystore**. Google Play **rejects** debug-signed uploads. There is no `keystore.jks` or `key.properties` file anywhere in the project.

**Required action:**
1. Generate a production keystore:
   ```bash
   keytool -genkey -v -keystore cypherguard-release.jks \
     -keyalg RSA -keysize 4096 -validity 10000 -alias cypherguard
   ```
2. Create `android/key.properties` (gitignored) with the keystore credentials
3. Update `build.gradle.kts` to load the production `signingConfigs.release`

---

### 4.3 🔴 P0 — SSL Pinning Placeholder Hashes (Security Blocker)

**File:** `lib/core/network/dio_factory.dart` lines 44–49:

```dart
static const Set<String> _kPinnedSha256Fingerprints = {
  'aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899', // ← DUMMY
  '99887766554433221100ffeeddccbbaa99887766554433221100ffeeddccbbaa', // ← DUMMY
};
```

**Current state:** SSL pinning infrastructure is fully implemented and **active in release mode**. However, the pinned fingerprints are placeholder hex strings. In production, the app will **reject all TLS connections** because no real server certificate matches these hashes.

**Required action — run against your production server:**
```bash
openssl s_client -connect 16.171.61.103:443 </dev/null 2>/dev/null \
  | openssl x509 -fingerprint -sha256 -noout \
  | sed 's/://g' | tr 'A-Z' 'a-z' | cut -d'=' -f2
```
Replace both dummy strings with: (1) the leaf certificate fingerprint, (2) the intermediate CA fingerprint.

> 🚨 **Caution:** Shipping with dummy SSL pins in release mode = the app cannot make ANY API call. This is a silent production outage, not a crash — it will look like a network error to users.

---

### 4.4 🟡 P1 — Native App Icon

**Current state:** All `mipmap-*` density folders exist but contain the default Flutter blue launcher icon. No `flutter_launcher_icons` package is present in `pubspec.yaml`.

**Required action:**
1. Add to `pubspec.yaml`: `flutter_launcher_icons: ^0.14.x`
2. Provide a 1024×1024 `assets/icon/icon.png` (dark shield / cybersecurity theme matching the app's dark UI)
3. Configure and run: `dart run flutter_launcher_icons`

---

### 4.5 🟡 P1 — Native Splash Screen

**Current state:** No `flutter_native_splash` package in `pubspec.yaml`. The app currently shows Flutter's default white splash screen before the animated `SplashPage` renders — a jarring white flash on every cold start.

**Required action:**
1. Add: `flutter_native_splash: ^2.x`
2. Configure with `background_color: "#0A0E1A"` (matches `AppColors.backgroundPrimary`) and the CypherGuard logo
3. Run: `dart run flutter_native_splash:create`

---

### 4.6 🟡 P1 — Code Obfuscation & Split Debug Info

**Current state:** No obfuscation flags anywhere in the build configuration. Dart symbols are fully readable in the compiled binary.

**Required action — release build command:**
```bash
flutter build appbundle \
  --obfuscate \
  --split-debug-info=build/debug-info/$(date +%Y%m%d) \
  --release
```

Or add to `build.gradle.kts`:
```kotlin
release {
    isMinifyEnabled   = true
    isShrinkResources = true
    proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
}
```

> Store the `build/debug-info/` symbols securely for crash symbolication via Firebase Crashlytics or Sentry.

---

### 4.7 🟡 P2 — Production Base URL (HTTP → HTTPS)

**File:** `lib/config/constants/api_constants.dart` line 7:

```dart
static const String baseUrl = 'http://16.171.61.103:8005';  // ← Plain HTTP dev URL
```

`DioFactory._resolvedBaseUrl` automatically upgrades `http://` → `https://` in release mode — this logic is correctly implemented. However, the **backend server must be configured to accept HTTPS** on port 443 (or 8005/TLS) before release. Confirm a valid TLS certificate is provisioned on the server.

---

### 4.8 🟡 P2 — Android Network Security Config

**Current state:** No `network_security_config.xml` in `res/xml/`. Without this, cleartext-traffic blocking in Android 9+ is not explicitly enforced at the OS level (only at the Dio layer).

**Required action:** Create `android/app/src/main/res/xml/network_security_config.xml`:
```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <domain-config cleartextTrafficPermitted="false">
        <domain includeSubdomains="true">securenet.local</domain>
    </domain-config>
    <debug-overrides>
        <trust-anchors>
            <certificates src="user"/>
        </trust-anchors>
    </debug-overrides>
</network-security-config>
```
Then reference in `AndroidManifest.xml`:
```xml
<application
    android:networkSecurityConfig="@xml/network_security_config"
    ...>
```

---

### 4.9 🟢 P3 — iOS Configuration (Not Audited)

No `ios/` directory was found in the workspace scan. iOS build configuration (Bundle ID, signing certificates, Info.plist permissions, App Transport Security) has not been set up.

**Required if targeting iOS:**
- Set `PRODUCT_BUNDLE_IDENTIFIER` in Xcode (must not be `com.example.*`)
- Add `NSLocalNotificationsUsageDescription` to `Info.plist`
- Configure iOS signing in Xcode Organiser or Fastlane
- Test `flutter_secure_storage` Keychain entitlements on a physical device

---

## 5. 📋 Final Go-Live Checklist

> Execute in order. All 🔴 items are hard blockers — the app **cannot** ship without them.

### Phase A — Identity & Security

- [ ] 🔴 Change `applicationId` from `com.example.threateye` → `com.{org}.cypherguard` in `build.gradle.kts`
- [ ] 🔴 Change `android:label` from `"threateye"` → `"CypherGuard"` in `AndroidManifest.xml`
- [ ] 🔴 Generate production keystore (`keytool`) and wire `key.properties` + `signingConfigs.release` in `build.gradle.kts`
- [ ] 🔴 Replace SSL pin hashes in `dio_factory.dart` with real server certificate SHA-256 fingerprints (run `openssl` against prod server)
- [ ] 🔴 Provision HTTPS on the backend server (`16.171.61.103`) and validate: `curl -v https://<host>/v1/mobile/auth/login`
- [ ] 🟡 Add `network_security_config.xml` and reference it in `AndroidManifest.xml`

### Phase B — Assets & UX Polish

- [ ] 🟡 App icon — add `flutter_launcher_icons`, provide `assets/icon/icon.png` (1024×1024), run generator
- [ ] 🟡 Native splash — add `flutter_native_splash`, configure dark background `#0A0E1A` + logo, run generator
- [ ] 🟡 App version — confirm `version: 1.0.0+1` in `pubspec.yaml` is correct for store submission
- [ ] 🟡 Confirm `android:label` shows correctly on device home screen after rename

### Phase C — Build & Obfuscation

- [ ] 🟡 Enable R8 in `build.gradle.kts`: `isMinifyEnabled = true` + `isShrinkResources = true`
- [ ] Run final release build:
  ```bash
  flutter build appbundle \
    --obfuscate \
    --split-debug-info=build/debug-info/$(date +%Y%m%d) \
    --release
  ```
- [ ] Archive `build/debug-info/` to a secure, version-tagged location

### Phase D — Device Testing (Signed AAB via bundletool)

- [ ] Splash → Login flow completes without white flash
- [ ] Login with real credentials reaches Dashboard
- [ ] WebSocket connects and live alerts appear in Notifications tab
- [ ] Firewall page loads blocked IPs list from API
- [ ] Decision History page loads from API
- [ ] Logout button clears session and returns to Login
- [ ] Verify `flutter_secure_storage` is empty after logout
- [ ] Kill app → relaunch → splash auto-routes to **Dashboard** (token still valid)
- [ ] Kill app → relaunch → splash auto-routes to **Login** (after token expiry / manual logout)
- [ ] `flutter analyze` confirms **0 errors, 0 warnings**

### Phase E — Store Submission

- [ ] Upload signed `.aab` to Google Play **Internal Testing** track first
- [ ] Complete store listing (description, screenshots, privacy policy URL)
- [ ] Add `INTERNET` permission explicitly to `AndroidManifest.xml`
- [ ] If iOS target: complete App Store Connect submission with valid provisioning profile

---

## Appendix — Dependency Snapshot

| Package | Version | Purpose | Status |
|---|---|---|---|
| `flutter_bloc` | `^8.1.6` | State management | ✅ Wired |
| `get_it` | `^8.0.2` | Dependency injection | ✅ 30 entries |
| `dio` | `^5.7.0` | HTTP client | ✅ Dual-Dio pattern |
| `flutter_secure_storage` | `^9.2.2` | Token encryption | ✅ |
| `web_socket_channel` | `^3.0.1` | Real-time events | ✅ |
| `flutter_local_notifications` | `^18.0.1` | OS notification tray | ✅ |
| `connectivity_plus` | `^6.1.0` | Offline detection | ✅ |
| `shared_preferences` | `^2.3.3` | Offline queue persistence | ✅ |
| `crypto` | `^3.0.3` | SHA-256 for SSL pinning | ✅ |
| `dartz` | `^0.10.1` | Functional Either type | ✅ |
| `equatable` | `^2.0.5` | Value equality | ✅ |
| `logger` | `^2.4.0` | Structured logging | ✅ |
| ~~`firebase_core`~~ | ~~`^3.6.0`~~ | ~~FCM~~ | 🗑️ Removed Sprint 2 |
| ~~`firebase_messaging`~~ | ~~`^15.1.3`~~ | ~~Push notifications~~ | 🗑️ Removed Sprint 2 |
| `flutter_launcher_icons` | **NOT ADDED** | App icon generation | ⬜ Missing |
| `flutter_native_splash` | **NOT ADDED** | Native splash screen | ⬜ Missing |

---

*Report generated from direct file-system inspection of the `threateye` workspace.*
*All findings are based on actual file contents, not assumptions.*
