# 📱 Flutter Project Progress Report — ThreatEye / ThreatPulse

> **Analysis Date:** 2026-04-18
> **Analyst:** Senior Flutter Engineer Review
> **Codebase:** `lib/` — package `threateye`

---

## 1. Project Overview

### What the App Does
**ThreatEye** (internally named **ThreatPulse** in `main.dart` and `app_constants.dart`) is a **mobile cybersecurity monitoring platform** for security operations teams. It provides:
- A dashboard showing system status, alert counts, and incident metrics
- An alert list with severity triage and a detail view
- A notifications feed for security events
- An AI chatbot (Gemini Pro) for threat explanation and mitigation guidance
- Placeholder scaffolding for Reports and Settings

### High-Level Architecture
**Feature-based Clean Architecture (data / domain / presentation per feature)**

```
lib/
├── app/           → empty shell (router lives in config/)
├── config/        → theme, router, constants
├── core/          → error, network, services, usecases, utils, widgets
└── features/
    ├── auth/          → Cubit + UI only (domain/data layers EMPTY)
    ├── alerts/        → Full stack (mock data)
    ├── chatbot/       → Full stack (real Gemini API)
    ├── dashboard/     → Full stack (mock data)
    ├── notifications/ → Full stack (mock data)
    ├── reports/       → All directories EMPTY
    ├── settings/      → All directories EMPTY
    └── splash/        → Animated UI, no Cubit (timer only)
```

> The architecture correctly separates layers in 5 of 8 features.
> `core/usecases/usecase.dart` defines `UseCase<T,P>` returning `Either<Failure, T>` (dartz),
> but **every concrete use case returns raw `Future<T>`** — the contract is never followed.

---

## 2. Fully Implemented Features ✅

### 2.1 Splash Screen
Complete UI with animations. No Cubit needed (pure timer navigation).

- `lib/features/splash/presentation/pages/splash_page.dart` — fade + scale + pulse via `AnimationController`
- `lib/features/splash/presentation/widgets/splash_logo.dart`
- `lib/features/splash/presentation/widgets/splash_app_name.dart`
- `lib/features/splash/presentation/widgets/splash_tagline.dart`
- `lib/features/splash/presentation/widgets/splash_loader.dart`
- `lib/features/splash/presentation/widgets/splash_version.dart`
- `lib/features/splash/presentation/widgets/splash_background_painter.dart`

Timer → `RouteNames.login` after `AppConstants.splashDurationMs` (2800 ms). `AnimationController` correctly disposed.

---

### 2.2 Login (Mock Auth)
UI + Cubit + complete mock flow. Single "Login to Dashboard" button with loading state. Shows "Demo Mode" badge.

- `lib/features/auth/presentation/pages/login_page.dart`
- `lib/features/auth/presentation/pages/cubit/auth_cubit.dart`
- `lib/features/auth/presentation/pages/cubit/auth_state.dart`

**States:** `AuthInitial`, `AuthLoading`, `AuthAuthenticated`, `AuthUnauthenticated`, `AuthError`

**Mock:** `login()` does `Future.delayed(1s)` → emits `AuthAuthenticated`. No credentials, no real API.
`AuthError` is defined but **never emitted**.

---

### 2.3 Dashboard
UI + Cubit + UseCase + Repository + mock model. Handles Loading / Loaded / Error states.

- `lib/features/dashboard/presentation/pages/dashboard_page.dart`
- `lib/features/dashboard/presentation/manager/dashboard_cubit.dart`
- `lib/features/dashboard/presentation/manager/dashboard_state.dart`
- `lib/features/dashboard/domain/usecases/get_dashboard_summary_usecase.dart`
- `lib/features/dashboard/domain/entities/dashboard_summary_entity.dart`
- `lib/features/dashboard/domain/repositories/dashboard_repository.dart`
- `lib/features/dashboard/data/repositories/dashboard_repository_impl.dart` → `DashboardSummaryModel.mock()`
- `lib/features/dashboard/data/models/dashboard_summary_model.dart` → hardcoded: `{totalAlerts:142, criticalAlerts:5, activeIncidents:2, systemStatus:'Warning'}`

Quick-action buttons navigate to `/alerts`, `/notifications`, `/chatbot`.

> ⚠️ Dead stub at `lib/features/auth/presentation/pages/dashboard_page.dart` (single "Go to Alerts" button). Router uses the correct one.

---

### 2.4 Alerts List + Alert Detail
Full clean-arch stack with mock data. "Ask AI" button deep-links to ChatPage with pre-built prompt.

- `lib/features/alerts/presentation/pages/alerts_page.dart` — list, severity colors, tap → detail
- `lib/features/alerts/presentation/pages/alert_detail_page.dart` — all entity fields + AI deep-link
- `lib/features/alerts/presentation/manager/alerts_cubit.dart`
- `lib/features/alerts/presentation/manager/alerts_state.dart`
- `lib/features/alerts/domain/usecases/get_alerts_usecase.dart`
- `lib/features/alerts/domain/entities/attack_alert_entity.dart`
- `lib/features/alerts/domain/repositories/alerts_repository.dart`
- `lib/features/alerts/data/repositories/alerts_repository_impl.dart` → 3 hardcoded `AttackAlertModel` objects
- `lib/features/alerts/data/models/attack_alert_model.dart`

> ⚠️ Dead stub at `lib/features/auth/presentation/pages/alerts_page.dart` (placeholder text only).

---

### 2.5 Notifications
Full clean-arch stack with mock data. Type-based icons (Alert / System). Tap → `AlertsPage`.

- `lib/features/notifications/presentation/pages/notifications_page.dart`
- `lib/features/notifications/presentation/cubit/notifications_cubit.dart`
- `lib/features/notifications/presentation/cubit/notifications_state.dart`
- `lib/features/notifications/domain/usecases/get_notifications_usecase.dart`
- `lib/features/notifications/domain/entities/notification_entity.dart`
- `lib/features/notifications/domain/repositories/notifications_repository.dart`
- `lib/features/notifications/data/repositories/notifications_repository_impl.dart` → 5 hardcoded `NotificationModel` objects
- `lib/features/notifications/data/models/notification_model.dart`

---

### 2.6 AI Chatbot — **Only feature with a real API call**
Full conversational UI with typing indicator, suggested prompts, auto-send from route arguments, live Gemini API.

- `lib/features/chatbot/presentation/pages/chat_page.dart`
- `lib/features/chatbot/presentation/cubit/chat_cubit.dart`
- `lib/features/chatbot/presentation/cubit/chat_state.dart`
- `lib/features/chatbot/domain/usecases/send_message_usecase.dart`
- `lib/features/chatbot/domain/entities/chat_message_entity.dart`
- `lib/features/chatbot/domain/repositories/chatbot_repository.dart`
- `lib/features/chatbot/data/repositories/chatbot_repository_impl.dart` → **live Dio call** to `generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent`
- `lib/features/chatbot/data/models/chat_message_model.dart`

---

## 3. Partially Implemented Features 🚧

### 3.1 Auth — Domain Layer Absent
- **Exists:** UI, Cubit, state classes
- **Missing:** `lib/features/auth/data/` and `lib/features/auth/domain/` are **completely empty directories**
- **Impact:** No entity, repository interface, or use case. Cannot swap in real auth without restructuring the cubit.

### 3.2 Core Infrastructure — Defined, Never Wired
All services are fully written but **zero are registered** in `lib/injection_container.dart` (the entire file is commented-out examples):

| Service | File | Status |
|---|---|---|
| `ApiClient` | `lib/core/network/api_client.dart` | Written, never instantiated |
| `DioFactory` | `lib/core/network/dio_factory.dart` | Written, never instantiated |
| `NetworkInfoImpl` | `lib/core/network/network_info.dart` | Written, never injected |
| `LocalNotificationService` | `lib/core/services/local_notification_service.dart` | Written, never registered |
| `SecureStorageService` | `lib/core/services/secure_storage_service.dart` | Written, never registered |
| `CacheService` | `lib/core/services/cache_service.dart` | Written, never registered |
| `LoggerService` | `lib/core/services/logger_service.dart` | Written, never registered |

### 3.3 Shared Widgets — Defined, Never Used
9 widgets in `lib/core/widgets/` — none imported in any feature page:
`AppButton`, `AppEmptyView`, `AppErrorView`, `AppLoader`, `AppTextField`, `CustomAppBar`, `InfoCard`, `SectionTitle`, `StatusChip`

### 3.4 `validators.dart` — Empty File
`lib/core/utils/validators.dart` — **0 bytes**

---

## 4. Mocked / Fake Logic ⚠️

| Feature | Mocked Element | File | Real Replacement |
|---|---|---|---|
| Auth login | `Future.delayed(1s)` → `AuthAuthenticated` | `auth_cubit.dart:13` | `POST /auth/login` via `ApiClient`, store JWT via `SecureStorageService` |
| Auth check | Always emits `AuthUnauthenticated` | `auth_cubit.dart:8` | Read + validate token from `SecureStorageService` |
| Dashboard | `DashboardSummaryModel.mock()` hardcoded numbers | `dashboard_repository_impl.dart:10` | `GET /dashboard/stats` |
| Alerts | 3 hardcoded `AttackAlertModel` instances | `alerts_repository_impl.dart:11-36` | `GET /alerts` with pagination |
| Notifications | 5 hardcoded `NotificationModel` instances | `notifications_repository_impl.dart:11-47` | `GET /notifications` + push service |
| Base URL | `'https://api.threatpulse.io/v1'` placeholder | `api_constants.dart:7` | Real backend URL |
| App name | `AppConstants.appName = 'ThreatPulse'` | `app_constants.dart:6` | Align with UI label 'ThreatEye' |
| Mock credentials | `mockAdminEmail`, `mockAdminPassword` | `app_constants.dart:27-28` | Remove before production |

> 🚨 **CRITICAL SECURITY RISK:**
> `lib/features/chatbot/data/repositories/chatbot_repository_impl.dart:9`
> contains a **hardcoded Gemini API key** directly in source code.
> This key is exposed in version control and must be rotated immediately.

---

## 5. Actual App Flow 🔄

Based strictly on `lib/config/router/app_router.dart` and `Navigator.pushNamed` calls:

```
App Launch
  └─► SplashPage  [lib/features/splash/presentation/pages/splash_page.dart]
        │  2800ms timer
        └─► LoginPage  [lib/features/auth/presentation/pages/login_page.dart]
              │  Button → AuthCubit.login() → AuthAuthenticated
              └─► DashboardPage  [lib/features/dashboard/presentation/pages/dashboard_page.dart]
                    ├─► [Button] AlertsPage  [lib/features/alerts/presentation/pages/alerts_page.dart]
                    │     └─► [Tap item] AlertDetailPage
                    │           └─► [Button "Ask AI"] ChatPage (pre-filled prompt via route args)
                    ├─► [Button] NotificationsPage
                    │     └─► [Tap item] AlertsPage
                    └─► [Button] ChatPage (empty prompt)
```

**Registered routes with no UI entry point:**
- `/reports` — no `case` in `AppRouter` switch
- `/settings` — not in `AppRouter` at all
- **No logout path** — `AuthCubit.logout()` exists but is never called from any widget

---

## 6. Missing Core Pieces 🛑

| Area | Finding | Evidence |
|---|---|---|
| **Dependency Injection** | `injection_container.dart` has zero real registrations | All 59 lines are comments |
| **Real API** | `ApiClient` & `DioFactory` exist but never instantiated | No import in any feature |
| **Auth token persistence** | `SecureStorageService` written but never injected | `auth_cubit.dart:8` always returns unauthenticated |
| **Form validation** | Login has no email/password fields — one button only | `login_page.dart`, `validators.dart` (0 bytes) |
| **Logout / session expiry** | No logout button; no token refresh; no path back to login | Router, `dashboard_page.dart` |
| **Reports feature** | All 3 layers are empty directories | `lib/features/reports/data|domain|presentation` |
| **Settings feature** | All 3 layers are empty directories | `lib/features/settings/data|domain|presentation` |
| **Error state UI** | All errors render raw `Text('Something went wrong...')` | `AppErrorView` exists in core but unused |
| **Loading state UI** | Raw `CircularProgressIndicator()` in every feature | `AppLoader` exists in core but unused |
| **Either/Failure pattern** | Base `UseCase` returns `Either<Failure,T>`; all concrete use cases return `Future<T>` | `core/usecases/usecase.dart` vs feature use cases |
| **Equatable on entities** | Entities don't extend `Equatable` | `AttackAlertEntity`, `DashboardSummaryEntity`, `NotificationEntity` |

---

## 7. Architecture & State Management Review 🧠

### ✅ Strengths
- Feature-based folder structure consistently applied across all active features
- `data / domain / presentation` separation present in 5 of 8 features
- Cubits use `emit()` correctly with well-defined state transitions
- `BlocConsumer` used properly in `ChatPage` (listener for scroll + builder for UI)
- Route argument passing works: `AlertDetailPage` → `ChatPage` pre-filled prompt
- `AnimationController` properly disposed in `SplashPage`
- `DioException` types correctly handled in `ApiClient`

### ❌ Weaknesses

| Issue | Evidence |
|---|---|
| **DI container empty** — cubits/repos instantiated inline inside `build()` | `dashboard_page.dart:15-18`, `alerts_page.dart:15-16`, `chat_page.dart:29-31` |
| **Cubit folder naming inconsistent** — auth uses `pages/cubit/`, others use `presentation/manager/` | `auth/presentation/pages/cubit/` vs `alerts/presentation/manager/` |
| **Base UseCase contract not followed** — returns `Future<T>` not `Either<Failure, T>` | All feature use cases vs `core/usecases/usecase.dart` |
| **`AuthState` does not extend `Equatable`** | `auth_state.dart:1` — `abstract class AuthState {}` |
| **Entities not `Equatable`** — may cause missed Bloc rebuilds | `attack_alert_entity.dart`, `dashboard_summary_entity.dart` |
| **9 core shared widgets never used** | All of `lib/core/widgets/*.dart` |
| **Dead code** — 3 stub files in `auth/presentation/pages/` | `alerts_page.dart` (321B), `dashboard_page.dart` (559B), `splash_page.dart` (BlocProvider version) |
| **Empty `lib/app/router/`** alongside working `lib/config/router/` | Structural duplication confusion |

---

## 8. Bugs, Risks & Technical Debt 🐛

### 🔴 Critical

| # | Bug | Location | Crash Scenario |
|---|---|---|---|
| 1 | **Hardcoded Gemini API key** in source code | `chatbot_repository_impl.dart:9` | Key exposure in version control |
| 2 | **Unchecked force-cast** `ModalRoute.of(context)!.settings.arguments as AttackAlertEntity` | `alert_detail_page.dart:11` | Crash if page opened without arguments |
| 3 | **`gemini-pro` model deprecated** by Google | `chatbot_repository_impl.dart:11` | API error or failure mid-demo |

### 🟡 Important

| # | Issue | Location |
|---|---|---|
| 4 | `late final ChatCubit _cubit` — if `initState` throws, `dispose()` will throw `LateInitializationError` | `chat_page.dart:18,47` |
| 5 | `AuthError` state defined but never emitted — dead class | `auth_cubit.dart`, `auth_state.dart:16` |
| 6 | No logout flow — cannot return to login post-auth | `dashboard_page.dart`, router |
| 7 | App name mismatch: `'ThreatPulse'` in code vs `'ThreatEye'` in UI and package | `main.dart:37`, `app_constants.dart:6` |
| 8 | `withOpacity()` deprecated in Flutter 3.x+ | `notifications_page.dart:81-82`, `login_page.dart:43` |

### 🟢 Technical Debt

| # | Issue |
|---|---|
| 9 | `dartz` declared in `pubspec.yaml` but `Either` never used in feature code |
| 10 | Mock credentials in `app_constants.dart:27-28` must be removed before production |
| 11 | Duplicate stub pages in `auth/presentation/pages/` should be deleted |
| 12 | Empty `lib/app/router/` directory should be removed |
| 13 | All 13 `Endpoints` constants defined but never called from any data source |

---

## 9. 🔥 Pre-Submission Priority

### 🔴 Critical (Must fix before demo)

1. **Rotate the Gemini API key** — `chatbot_repository_impl.dart:9`. Use `--dart-define` or a secrets solution. Key is in version control.
2. **Update Gemini model** — change `gemini-pro` → `gemini-1.5-flash` or `gemini-2.0-flash` in `chatbot_repository_impl.dart:11`.
3. **Null guard on `AlertDetailPage`** — add null check on `ModalRoute.of(context)!.settings.arguments` before the force-cast at `alert_detail_page.dart:11`.
4. **Add logout** — even a simple `AppBar` action calling `AuthCubit.logout()` + `Navigator.pushReplacementNamed(context, RouteNames.login)`.
5. **Fix app name** — align `main.dart:37`, `pubspec.yaml:2`, and `app_constants.dart:6` to one consistent name.

### 🟡 Important

6. Register at least `ApiClient` and `DioFactory` in `injection_container.dart` so DI is not purely dead code.
7. Replace raw `CircularProgressIndicator` and `Text('Something went wrong...')` with `AppLoader` and `AppErrorView` from `core/widgets/`.
8. Add `extends Equatable` (with `props`) to `AuthState`, `AttackAlertEntity`, `DashboardSummaryEntity`.
9. Delete dead stub files in `lib/features/auth/presentation/pages/`.

### 🟢 Optional

10. Replace `withOpacity()` with `.withValues(alpha: ...)`.
11. Align or remove the base `UseCase<T, P>` `Either` contract to match actual use cases.
12. Delete the empty `lib/app/router/` directory.

---

## 10. Demo Readiness Score

## 🎯 62 / 100

| Dimension | Score | Rationale |
|---|---|---|
| Navigation flow | 14/20 | Core flow works; no logout; reports/settings absent |
| Feature completeness | 14/20 | 5/8 features have full flow; 2 completely empty |
| Data & state | 12/20 | Consistent contextual mock data; only chatbot has real API |
| Code quality | 12/20 | Clean-arch structure present; DI empty; contract violations |
| Stability / crash risk | 10/20 | Live crash risk on `AlertDetailPage`; deprecated Gemini model; exposed API key |

**Justification:** The `Splash → Login → Dashboard → Alerts → AI Chatbot` path works and can support a focused demo. The 3 critical issues (exposed key, deprecated model, crash-risk cast) are concrete demo-breakers. Fixing the 5 critical items would push the score to approximately **78/100**.

---

## 11. Overall Progress

## 📊 ~42% Complete

| Feature | Progress | Blocker |
|---|---|---|
| Splash | ██████████ 100% | — |
| Chatbot | █████████░ 85% | Deprecated model, API key exposed |
| Auth | ███████░░░ 70% | No domain layer, mock only, no real form |
| Dashboard | ███████░░░ 70% | Mock data, DI not wired |
| Alerts | ███████░░░ 70% | Mock data, DI not wired, dead duplicate file |
| Notifications | ███████░░░ 70% | Mock data, DI not wired |
| Core infrastructure | ███░░░░░░░ 30% | All services defined but never registered or used |
| Reports | ░░░░░░░░░░ 0% | Empty directories |
| Settings | ░░░░░░░░░░ 0% | Empty directories |

### What is preventing 100%

1. No real backend API integration — all features except chatbot use `Future.delayed` + hardcoded objects
2. `injection_container.dart` has zero real registrations — DI is structurally non-functional
3. Auth domain layer entirely absent (`auth/data/` and `auth/domain/` empty)
4. Reports and Settings not started
5. `validators.dart` is 0 bytes — no form validation exists
6. 9 core shared widgets and 4 core services are defined but never consumed by any feature
7. Base `UseCase` contract (`Either<Failure, T>`) not followed by any concrete use case
