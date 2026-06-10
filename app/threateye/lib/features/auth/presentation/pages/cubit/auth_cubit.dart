import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:threateye/config/constants/api_constants.dart';
import 'package:threateye/core/error/failures.dart';
import 'package:threateye/core/services/offline_queue_service.dart';
import 'package:threateye/core/services/websocket_manager_service.dart';
import 'package:threateye/core/usecases/usecase.dart';
import 'package:threateye/features/auth/domain/usecases/login_usecase.dart';
import 'package:threateye/features/auth/domain/usecases/logout_usecase.dart';
import 'package:threateye/injection_container.dart';
import 'auth_state.dart';

/// Presentation-layer state machine for authentication.
///
/// Depends on [LoginUseCase] and [LogoutUseCase] resolved from [GetIt].
/// The no-argument constructor is intentional — [LoginPage] creates it inline
/// with `create: (_) => AuthCubit()` and must not be changed.
///
/// **Phase 5:** connects the singleton [WebSocketManagerService] on a
/// successful login and disconnects it on logout.
///
/// **Phase 6 — Secure Memory Wipe:**
/// [logout] now executes a strict, ordered teardown sequence before emitting
/// [AuthUnauthenticated]:
///   1. Pause the [OfflineQueueService] — prevents it from firing a queued
///      POST with the about-to-be-wiped access token.
///   2. Disconnect the WebSocket — intentional disconnect so no reconnect
///      is attempted with the stale token.
///   3. Call [LogoutUseCase] — POSTs to the server revocation endpoint and,
///      in its `finally` block, calls [SecureStorageService.deleteAll()] to
///      wipe every token and role from encrypted storage.
///   4. Clear the offline decision queue — queued decisions belong to this
///      analyst session and must not leak to the next user.
///   5. Emit [AuthUnauthenticated] — triggers navigation back to LoginPage.
class AuthCubit extends Cubit<AuthState> {
  late final LoginUseCase            _loginUseCase;
  late final LogoutUseCase           _logoutUseCase;
  late final WebSocketManagerService _wsManager;
  late final OfflineQueueService     _offlineQueue;

  AuthCubit() : super(const AuthInitial()) {
    _loginUseCase  = sl<LoginUseCase>();
    _logoutUseCase = sl<LogoutUseCase>();
    _wsManager     = sl<WebSocketManagerService>();
    _offlineQueue  = sl<OfflineQueueService>();
  }

  // ── login ──────────────────────────────────────────────────────────────────

  Future<void> login(String email, String password) async {
    final trimmedEmail = email.trim();
    if (trimmedEmail.isEmpty || password.isEmpty) {
      emit(const AuthError('Please enter your email and password.'));
      return;
    }

    emit(const AuthLoading());

    final result = await _loginUseCase(
      LoginParams(email: trimmedEmail, password: password),
    );

    result.fold(
      (failure) => emit(AuthError(_mapFailure(failure))),
      (auth) {
        emit(AuthAuthenticated(role: auth.role));
        // Phase 5: open the WebSocket now that we have a valid session.
        _wsManager.connect();
        // Phase 6: resume the queue so any previously parked decisions
        // (from an offline session before login) are delivered immediately.
        _offlineQueue.resume();
      },
    );
  }

  // ── logout ─────────────────────────────────────────────────────────────────

  /// Secure, ordered memory-wipe sequence.
  ///
  /// Every step is guarded so a failure in one phase never silently blocks
  /// the later phases. The `finally` block **guarantees** that
  /// [AuthUnauthenticated] is always emitted — even if the API call or
  /// storage wipe throws an unexpected error.
  Future<void> logout() async {
    try {
      // ── Step 1: Pause the offline queue ───────────────────────────────────
      // Must happen BEFORE token wipe so a mid-flight flush cannot fire a
      // POST with an invalidated Bearer token.
      _offlineQueue.pause();

      // ── Step 2: Disconnect WebSocket ──────────────────────────────────────
      // Sets intentional=true so the reconnect timer is never armed.
      _wsManager.disconnect();

      // ── Step 3: Server-side revocation + SecureStorage wipe ───────────────
      // LogoutUseCase → AuthRemoteDataSource.logout():
      //   • POSTs to /v1/mobile/auth/logout (best-effort — fire & forget).
      //   • In finally{}: calls SecureStorageService.deleteAll() to destroy
      //     every encrypted key (access_token, refresh_token, user_role).
      // Failure is non-critical — we always continue to step 4.
      try {
        await _logoutUseCase(const NoParams());
      } catch (_) {
        // Swallow — local wipe must always complete regardless of API state.
      }

      // ── Step 4: Purge offline queue ────────────────────────────────────────
      // Queued decisions belong to this analyst — do not hand them to whoever
      // logs in next.
      try {
        await _offlineQueue.clear();
      } catch (_) {}
    } finally {
      // ── Step 5: Emit unauthenticated → navigates to LoginPage ─────────────
      // Placed in finally so it fires even if an unexpected exception escapes
      // the inner try blocks above.
      if (!isClosed) emit(const AuthUnauthenticated());
    }
  }

  // ── helpers ────────────────────────────────────────────────────────────────

  String _mapFailure(Failure failure) {
    if (failure is ValidationFailure)   return failure.message;
    if (failure is NetworkFailure)      return failure.message;
    if (failure is UnauthorizedFailure) return 'Invalid email or password.';

    if (failure is ServerFailure) {
      // Branch on the machine-readable error code first (most precise).
      switch (failure.errorCode) {
        case ApiConstants.errAuthInvalid:
          return 'Invalid email or password.';
        case ApiConstants.errRateLimited:
          return 'Too many attempts. Please wait 60 seconds and try again.';
        case ApiConstants.errAccountLocked:
          return 'Account locked after too many failed attempts. '
              'Please try again in 15 minutes or contact your administrator.';
        case ApiConstants.errAuthTokenExpired:
          // Should be handled by AuthInterceptor before reaching here.
          return 'Your session has expired. Please log in again.';
      }
      // Fall back to HTTP status code for unmapped codes.
      if (failure.statusCode == 429) {
        return 'Too many attempts. Please wait and try again.';
      }
      return failure.message;
    }

    return failure.message;
  }
}
