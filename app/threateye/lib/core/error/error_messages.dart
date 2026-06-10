/// Centralized user-facing error message strings.
class ErrorMessages {
  ErrorMessages._();

  static const String networkError =
      'Unable to connect. Please check your internet connection.';

  static const String serverError =
      'Server error. Please try again later.';

  static const String unauthorizedError =
      'Your session has expired. Please log in again.';

  static const String notFoundError =
      'The requested data could not be found.';

  static const String cacheError =
      'Failed to load cached data. Please refresh.';

  static const String unexpectedError =
      'Something went wrong. Please try again.';

  static const String loginFailed =
      'Invalid credentials. Please try again.';

  static const String emptyAlerts =
      'No alerts found at this time.';

  static const String emptyNotifications =
      'No notifications yet.';
}