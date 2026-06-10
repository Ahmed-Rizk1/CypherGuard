import 'package:equatable/equatable.dart';

/// Domain entity representing a successfully authenticated session.
/// Carries all fields returned by the login / refresh endpoints.
class AuthEntity extends Equatable {
  final String accessToken;
  final String refreshToken;
  final String tokenType;
  final int expiresIn;
  final String role;

  const AuthEntity({
    required this.accessToken,
    required this.refreshToken,
    required this.tokenType,
    required this.expiresIn,
    required this.role,
  });

  @override
  List<Object?> get props =>
      [accessToken, refreshToken, tokenType, expiresIn, role];
}
