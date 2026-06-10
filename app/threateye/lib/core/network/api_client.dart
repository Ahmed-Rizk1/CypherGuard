import 'package:dio/dio.dart';

import '../error/exceptions.dart';

/// HTTP client wrapper around [Dio].
///
/// Every method translates [DioException]s into typed [AppException]s so that
/// higher layers never import Dio directly.
class ApiClient {
  final Dio _dio;

  ApiClient(this._dio);

  // ── GET ────────────────────────────────────────────────────────────────────

  Future<Response> get(
    String path, {
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    try {
      return await _dio.get(
        path,
        queryParameters: queryParameters,
        options: options,
      );
    } on DioException catch (e) {
      throw _handleDioError(e);
    }
  }

  // ── POST ───────────────────────────────────────────────────────────────────

  Future<Response> post(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    try {
      return await _dio.post(
        path,
        data: data,
        queryParameters: queryParameters,
        options: options,
      );
    } on DioException catch (e) {
      throw _handleDioError(e);
    }
  }

  // ── PATCH ──────────────────────────────────────────────────────────────────

  /// Used for partial updates, e.g. `PATCH /v1/mobile/alerts/{id}`.
  Future<Response> patch(
    String path, {
    dynamic data,
    Options? options,
  }) async {
    try {
      return await _dio.patch(path, data: data, options: options);
    } on DioException catch (e) {
      throw _handleDioError(e);
    }
  }

  // ── PUT ────────────────────────────────────────────────────────────────────

  Future<Response> put(
    String path, {
    dynamic data,
    Options? options,
  }) async {
    try {
      return await _dio.put(path, data: data, options: options);
    } on DioException catch (e) {
      throw _handleDioError(e);
    }
  }

  // ── DELETE ─────────────────────────────────────────────────────────────────

  Future<Response> delete(
    String path, {
    dynamic data,
    Options? options,
  }) async {
    try {
      return await _dio.delete(path, data: data, options: options);
    } on DioException catch (e) {
      throw _handleDioError(e);
    }
  }

  // ── Error mapping ──────────────────────────────────────────────────────────

  AppException _handleDioError(DioException e) {
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.receiveTimeout:
      case DioExceptionType.sendTimeout:
        return const NetworkException(message: 'Connection timed out.');
      case DioExceptionType.connectionError:
        return const NetworkException();
      case DioExceptionType.badResponse:
        final statusCode = e.response?.statusCode;
        final body       = e.response?.data;

        // Extract machine-readable error code from the API envelope:
        // { "success": false, "error": { "code": "RATE_LIMITED", ... } }
        final errorCode = _extractErrorCode(body);

        if (statusCode == 401) {
          return UnauthorizedException(
            message: _extractMessage(body) ??
                'Unauthorized. Please log in again.',
          );
        }
        if (statusCode == 404) {
          return const NotFoundException();
        }
        return ServerException(
          message:   _extractMessage(body) ?? 'Server error.',
          statusCode: statusCode,
          errorCode:  errorCode,
        );
      default:
        return ServerException(message: e.message ?? 'Unexpected error.');
    }
  }

  /// Reads `error.code` from the standard API error envelope.
  String? _extractErrorCode(dynamic body) {
    try {
      if (body is Map) {
        final err = body['error'];
        if (err is Map) return err['code'] as String?;
      }
    } catch (_) {}
    return null;
  }

  /// Reads the human-readable message from the API error envelope.
  String? _extractMessage(dynamic body) {
    try {
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
