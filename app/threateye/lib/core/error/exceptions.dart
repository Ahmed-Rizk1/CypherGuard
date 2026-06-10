/// Base exception for all app-level exceptions.
abstract class AppException implements Exception {
  final String message;
  final int? statusCode;

  const AppException({required this.message, this.statusCode});

  @override
  String toString() => 'AppException: $message (code: $statusCode)';
}

/// Thrown when a server/API request fails.
///
/// [errorCode] carries the machine-readable code from the API envelope
/// (e.g. `AUTH_INVALID`, `RATE_LIMITED`, `ACCOUNT_LOCKED`).
/// Use it to distinguish errors that share the same HTTP status code.
class ServerException extends AppException {
  /// Machine-readable code from `error.code` in the API response body.
  final String? errorCode;

  const ServerException({
    required super.message,
    super.statusCode,
    this.errorCode,
  });
}

/// Thrown when there is no internet connection.
class NetworkException extends AppException {
  const NetworkException({super.message = 'No internet connection.'});
}

/// Thrown when authentication fails or token is invalid.
class UnauthorizedException extends AppException {
  const UnauthorizedException(
      {super.message = 'Unauthorized. Please log in again.'});
}

/// Thrown when the requested resource is not found.
class NotFoundException extends AppException {
  const NotFoundException(
      {super.message = 'The requested resource was not found.'});
}

/// Thrown when the local cache read/write fails.
class CacheException extends AppException {
  const CacheException(
      {super.message = 'Local cache error.', super.statusCode});
}

/// Thrown when input validation fails locally.
class ValidationException extends AppException {
  const ValidationException({required super.message});
}