import 'package:dartz/dartz.dart';
import 'package:threateye/core/error/failures.dart';
import 'package:threateye/features/auth/domain/entities/auth_entity.dart';

/// Contract for authentication operations.
/// Data layer must implement this; domain + presentation layers depend only on
/// this abstraction — never on concrete implementations.
abstract class AuthRepository {
  /// Authenticates with [email] and [password].
  /// Returns [AuthEntity] on success, [Failure] on error.
  Future<Either<Failure, AuthEntity>> login(String email, String password);

  /// Exchanges the stored single-use [refreshToken] for a new token pair.
  /// Returns the fresh [AuthEntity] on success, [Failure] on error.
  Future<Either<Failure, AuthEntity>> refreshToken(String refreshToken);

  /// Invalidates the access token server-side and clears local secure storage.
  Future<Either<Failure, void>> logout();
}
