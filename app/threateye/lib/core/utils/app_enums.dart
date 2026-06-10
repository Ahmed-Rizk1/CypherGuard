/// Alert severity levels used across the app.
enum AlertSeverity { critical, high, medium, low }

/// Types of cyber attacks the system can detect.
enum AttackType {
  ddos,
  sqlInjection,
  bruteForce,
  xss,
  malware,
  suspiciousNetwork,
  unknown,
}

/// Status of an alert.
enum AlertStatus { active, resolved, escalated, falsePositive }

/// App-wide loading / operation states.
enum RequestStatus { initial, loading, success, failure }

/// Theme modes.
enum AppThemeMode { dark, light, system }

/// Notification types.
enum NotificationType { critical, warning, info, resolved }