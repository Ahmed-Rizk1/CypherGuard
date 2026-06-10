import 'package:equatable/equatable.dart';

/// Base class for all domain-level failures.
/// Failures are returned from use cases via Either<Failure, T>.
abstract class Failure extends Equatable {
  final String message;

  const Failure({required this.message});

  @override
  List<Object?> get props => [message];
}

/// Failure caused by a server-side error.
///
/// [errorCode] mirrors the machine-readable code in the API error envelope
/// (e.g. `RATE_LIMITED`, `ACCOUNT_LOCKED`). Cubits can branch on it to show
/// specific messages without coupling to HTTP status codes.
class ServerFailure extends Failure {
  final int? statusCode;

  /// Machine-readable code from `error.code` in the API response body.
  final String? errorCode;

  const ServerFailure({
    required super.message,
    this.statusCode,
    this.errorCode,
  });

  @override
  List<Object?> get props => [message, statusCode, errorCode];
}

/// Failure caused by network connectivity issues.
class NetworkFailure extends Failure {
  const NetworkFailure(
      {super.message = 'No internet connection. Please check your network.'});
}

/// Failure caused by an authentication error (401 / expired token).
class UnauthorizedFailure extends Failure {
  const UnauthorizedFailure(
      {super.message = 'Session expired. Please log in again.'});
}

/// Failure caused by a local cache error.
class CacheFailure extends Failure {
  const CacheFailure({super.message = 'Failed to load cached data.'});
}

/// Failure caused by a validation error.
class ValidationFailure extends Failure {
  const ValidationFailure({required super.message});
}

/// Generic unexpected failure.
class UnexpectedFailure extends Failure {
  const UnexpectedFailure({super.message = 'An unexpected error occurred.'});
}

/// Failure caused by a 404 — the requested resource does not exist.
///
/// Use this instead of [ServerFailure] when you need the UI to show a
/// specific "not found" message (e.g., "This alert no longer exists").
class NotFoundFailure extends Failure {
  const NotFoundFailure({super.message = 'The requested resource was not found.'});
}