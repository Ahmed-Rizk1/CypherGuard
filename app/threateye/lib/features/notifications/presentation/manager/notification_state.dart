// ─── Notification States ───────────────────────────────────────────────────

abstract class NotificationState {}

/// Initial state before [NotificationCubit.init] is called.
class NotificationInitial extends NotificationState {}

/// FCM token obtained and registration call in-flight.
class NotificationRegistering extends NotificationState {}

/// Device successfully registered with the backend.
class NotificationRegistered extends NotificationState {}

/// FCM is unavailable on this device (emulator, permission denied, etc.).
/// Not a hard error — the app continues to work without push notifications.
class NotificationUnavailable extends NotificationState {
  final String reason;
  NotificationUnavailable(this.reason);
}

/// Backend registration call failed (network / server error).
/// Logged silently — never surfaced to the user as a blocking UI error.
class NotificationRegistrationFailed extends NotificationState {
  final String message;
  NotificationRegistrationFailed(this.message);
}
