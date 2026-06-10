/// Application-wide constants used across all features.
class AppConstants {
  AppConstants._();

  // App metadata
  static const String appName = 'CypherGuard';
  static const String appVersion = '1.0.0';

  // Splash screen duration (milliseconds)
  static const int splashDurationMs = 2800;

  // Pagination defaults
  static const int defaultPageSize = 20;

  // Animation durations
  static const int shortAnimationMs = 200;
  static const int mediumAnimationMs = 400;
  static const int longAnimationMs = 700;

  // Local storage keys
  static const String keyIsLoggedIn = 'is_logged_in';
  static const String keyAuthToken = 'auth_token';
  static const String keyThemeMode = 'theme_mode';
  static const String keyUserData = 'user_data';

  // Mock admin credentials (Phase 2 — auth mock)
  static const String mockAdminEmail = 'admin@cypherguard.io';
  static const String mockAdminPassword = 'Admin@1234';

  // Severity levels
  static const String severityCritical = 'Critical';
  static const String severityHigh = 'High';
  static const String severityMedium = 'Medium';
  static const String severityLow = 'Low';
}