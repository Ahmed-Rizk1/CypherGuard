import 'package:equatable/equatable.dart';

abstract class AuthState extends Equatable {
  const AuthState();

  @override
  List<Object?> get props => [];
}

class AuthInitial extends AuthState {
  const AuthInitial();
}

class AuthLoading extends AuthState {
  const AuthLoading();
}

/// User is authenticated. Carries the [role] returned by the API
/// (e.g. "analyst", "admin") so the UI can display it.
class AuthAuthenticated extends AuthState {
  final String role;

  const AuthAuthenticated({this.role = 'analyst'});

  @override
  List<Object?> get props => [role];
}

class AuthUnauthenticated extends AuthState {
  const AuthUnauthenticated();
}

class AuthError extends AuthState {
  final String message;

  const AuthError(this.message);

  @override
  List<Object?> get props => [message];
}
