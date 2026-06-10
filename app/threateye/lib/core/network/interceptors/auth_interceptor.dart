import 'dart:async';

import 'package:dio/dio.dart';
import 'package:threateye/config/constants/api_constants.dart';
import 'package:threateye/config/router/route_names.dart';
import 'package:threateye/core/services/logger_service.dart';
import 'package:threateye/core/services/navigation_service.dart';
import 'package:threateye/core/services/secure_storage_service.dart';
import 'package:threateye/features/auth/data/datasources/auth_remote_data_source.dart';

/// Dio interceptor that handles JWT lifecycle for all authenticated requests.
///
/// ### Responsibilities
/// 1. **onRequest** — attaches `Authorization: Bearer <token>` to every
///    non-auth request automatically.
/// 2. **onError (401)** — attempts a token refresh exactly once (thread-safe),
///    then retries the original request with the new token.
/// 3. **Force logout** — if the refresh itself fails (expired, revoked, network
///    outage), it wipes secure storage and redirects to `/login` immediately.
///
/// ### Thread-Safety
/// [_refreshCompleter] acts as a mutex.  The **first** request that hits a 401
/// creates the `Completer` and owns the refresh call.  Every **subsequent** 401
/// that arrives while the refresh is in-flight skips the second call and simply
/// awaits the same `Future<bool>` — receiving `true` (retry) or `false` (fail).
class AuthInterceptor extends Interceptor {
  final SecureStorageService _storage;
  final AuthRemoteDataSource _authDataSource;

  /// Non-null while a token refresh is in progress.
  Completer<bool>? _refreshCompleter;

  /// Reference to the parent Dio — set via [init] after construction to avoid
  /// a circular dependency in the DI container.
  late final Dio _dio;

  /// Extra key used to mark retry requests so they skip this interceptor's
  /// error handler and do not trigger an infinite retry loop.
  static const _retryKey = '_authRetry';

  // Auth paths that must never have the Authorization header added
  // and must not trigger a refresh on 401.
  static const _loginPath   = '/v1/mobile/auth';
  static const _refreshPath = '/v1/mobile/auth/refresh';
  static const _logoutPath  = '/v1/mobile/auth/logout';

  AuthInterceptor({
    required SecureStorageService storage,
    required AuthRemoteDataSource authDataSource,
  })  : _storage = storage,
        _authDataSource = authDataSource;

  /// Must be called once after DI wires the parent Dio to avoid circular refs.
  void init(Dio dio) => _dio = dio;

  // ── onRequest ──────────────────────────────────────────────────────────────

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    // Skip auth-related paths — they carry their own credentials.
    if (_isAuthPath(options.path)) return handler.next(options);

    final token = await _storage.read(ApiConstants.accessTokenKey);
    if (token != null && token.isNotEmpty) {
      options.headers['Authorization'] =
          '${ApiConstants.bearerPrefix} $token';
    }
    handler.next(options);
  }

  // ── onError ────────────────────────────────────────────────────────────────

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    final statusCode = err.response?.statusCode;
    final isRetry    = err.requestOptions.extra[_retryKey] == true;

    // Only intercept 401 on protected endpoints — and never on retry attempts.
    if (statusCode != 401 || isRetry || _isAuthPath(err.requestOptions.path)) {
      return handler.next(err);
    }

    LoggerService.warning(
      '[AuthInterceptor] 401 on ${err.requestOptions.path} — attempting refresh.',
    );

    // ── Thread-safe gate ────────────────────────────────────────────────────
    if (_refreshCompleter != null) {
      // A refresh is already in-flight — wait for the result.
      LoggerService.info('[AuthInterceptor] Waiting for ongoing refresh...');
      final succeeded = await _refreshCompleter!.future;
      if (succeeded) {
        return handler.resolve(await _retry(err.requestOptions));
      }
      return handler.next(err);
    }

    // We are the FIRST 401 — own the refresh.
    _refreshCompleter = Completer<bool>();
    try {
      final storedRefreshToken =
          await _storage.read(ApiConstants.refreshTokenKey);

      if (storedRefreshToken == null || storedRefreshToken.isEmpty) {
        throw Exception('No refresh token found in secure storage.');
      }

      // Calls the raw-Dio auth data source — bypasses this interceptor.
      await _authDataSource.refreshToken(storedRefreshToken);
      // Tokens already persisted inside AuthRemoteDataSourceImpl.

      _refreshCompleter!.complete(true);
      LoggerService.info('[AuthInterceptor] Token refreshed — retrying original request.');
      return handler.resolve(await _retry(err.requestOptions));
    } catch (e) {
      LoggerService.error('[AuthInterceptor] Refresh failed — forcing logout.', e);
      _refreshCompleter!.complete(false);
      await _forceLogout();
      return handler.next(err);
    } finally {
      _refreshCompleter = null;
    }
  }

  // ── helpers ────────────────────────────────────────────────────────────────

  /// Replays [original] through the parent [_dio] with:
  ///   • the fresh access token injected into the `Authorization` header, and
  ///   • the [_retryKey] extra flag set to `true` to skip re-entry on failure.
  Future<Response<dynamic>> _retry(RequestOptions original) async {
    final newToken = await _storage.read(ApiConstants.accessTokenKey);
    return _dio.fetch(
      original.copyWith(
        headers: {
          ...original.headers,
          'Authorization': '${ApiConstants.bearerPrefix} $newToken',
        },
        extra: {
          ...original.extra,
          _retryKey: true,
        },
      ),
    );
  }

  /// Clears all locally persisted credentials and navigates to the login screen.
  Future<void> _forceLogout() async {
    await _storage.deleteAll();
    NavigationService.pushReplacementNamed(RouteNames.login);
  }

  /// Returns `true` for paths that should bypass this interceptor entirely.
  bool _isAuthPath(String path) =>
      path == _loginPath ||
      path == _refreshPath ||
      path == _logoutPath;
}
