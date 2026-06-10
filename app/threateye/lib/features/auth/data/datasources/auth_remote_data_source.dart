import 'package:dio/dio.dart';
import 'package:threateye/config/constants/api_constants.dart';
import 'package:threateye/core/error/exceptions.dart';
import 'package:threateye/core/services/secure_storage_service.dart';

import '../models/auth_response_model.dart';
import '../models/refresh_token_request_dto.dart';

abstract class AuthRemoteDataSource {
  Future<AuthResponseModel> login(String email, String password);

  /// Exchanges [refreshToken] for a new token pair.
  /// Persists the new tokens to secure storage before returning.
  Future<AuthResponseModel> refreshToken(String refreshToken);

  Future<void> logout();
}

class AuthRemoteDataSourceImpl implements AuthRemoteDataSource {
  final Dio _dio;
  final SecureStorageService _storage;

  static const _loginPath   = '/v1/mobile/auth';
  static const _refreshPath = '/v1/mobile/auth/refresh';
  static const _logoutPath  = '/v1/mobile/auth/logout';

  AuthRemoteDataSourceImpl(this._dio, this._storage);

  // ── login ──────────────────────────────────────────────────────────────────

  @override
  Future<AuthResponseModel> login(String email, String password) async {
    try {
      final response = await _dio.post(
        _loginPath,
        data: {'email': email, 'password': password},
        options: Options(headers: {'Content-Type': 'application/json'}),
      );

      final body = response.data as Map<String, dynamic>;

      // API-level failure with 2xx HTTP status (success: false in body)
      if (body['success'] == false) {
        final err = body['error'] as Map<String, dynamic>?;
        throw ServerException(
          message:   err?['message'] as String? ?? 'Login failed.',
          errorCode: err?['code']    as String?,
        );
      }

      final model = AuthResponseModel.fromJson(body);
      await _persistTokens(model);
      return model;
    } on ServerException {
      rethrow;
    } on UnauthorizedException {
      rethrow;
    } on DioException catch (e) {
      throw _parseDioException(e);
    }
  }

  // ── refreshToken ───────────────────────────────────────────────────────────

  @override
  Future<AuthResponseModel> refreshToken(String refreshToken) async {
    try {
      final response = await _dio.post(
        _refreshPath,
        data: RefreshTokenRequestDto(refreshToken: refreshToken).toJson(),
        options: Options(headers: {'Content-Type': 'application/json'}),
      );

      final body = response.data as Map<String, dynamic>;

      if (body['success'] == false) {
        final err = body['error'] as Map<String, dynamic>?;
        // Any API-level failure on refresh = session is dead
        throw UnauthorizedException(
          message: err?['message'] as String? ?? 'Token refresh failed.',
        );
      }

      final model = AuthResponseModel.fromJson(body);
      await _persistTokens(model);
      return model;
    } on UnauthorizedException {
      rethrow;
    } on DioException catch (e) {
      // 401 on refresh → session expired, must re-login
      throw (e.response?.statusCode == 401)
          ? UnauthorizedException(
              message: _errorMessage(e) ?? 'Session expired.',
            )
          : _parseDioException(e);
    }
  }

  // ── logout ─────────────────────────────────────────────────────────────────

  @override
  Future<void> logout() async {
    try {
      final token = await _storage.read(ApiConstants.accessTokenKey);
      if (token != null && token.isNotEmpty) {
        await _dio.post(
          _logoutPath,
          options: Options(
            headers: {'Authorization': 'Bearer $token'},
          ),
        );
      }
    } finally {
      // Always wipe local storage — even if the server call fails.
      await _storage.deleteAll();
    }
  }

  // ── helpers ────────────────────────────────────────────────────────────────

  Future<void> _persistTokens(AuthResponseModel model) async {
    await _storage.write(ApiConstants.accessTokenKey,  model.accessToken);
    await _storage.write(ApiConstants.refreshTokenKey, model.refreshToken);
    await _storage.write(ApiConstants.userRoleKey,     model.role);
  }

  /// Converts a [DioException] with a non-2xx response into a typed
  /// [AppException] carrying the API error code where available.
  AppException _parseDioException(DioException e) {
    final statusCode = e.response?.statusCode;
    final errorCode  = _errorCode(e);
    final message    = _errorMessage(e);


    if (e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.receiveTimeout    ||
        e.type == DioExceptionType.sendTimeout       ||
        e.type == DioExceptionType.connectionError) {
      return NetworkException(
        message: message ?? 'No internet connection.',
      );
    }

    if (statusCode == 401) {
      return UnauthorizedException(
        message: message ?? 'Unauthorized. Please log in again.',
      );
    }

    return ServerException(
      message:    message   ?? 'Server error ($statusCode).',
      statusCode: statusCode,
      errorCode:  errorCode,
    );
  }

  /// Extracts `error.code` from the standard API envelope.
  String? _errorCode(DioException e) {
    try {
      final body = e.response?.data;
      if (body is Map) {
        final err = body['error'];
        if (err is Map) return err['code'] as String?;
      }
    } catch (_) {}
    return null;
  }

  /// Extracts the human-readable message from the standard API envelope.
  String? _errorMessage(DioException e) {
    try {
      final body = e.response?.data;
      if (body is Map) {
        final err = body['error'];
        if (err is Map && err['message'] != null) {
          return err['message'] as String;
        }
        if (body['message'] != null) return body['message'] as String;
      }
    } catch (_) {}
    return null;
  }
}
