import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:dio/dio.dart';
import 'package:dio/io.dart';
import 'package:flutter/foundation.dart' show kReleaseMode, debugPrint;
import 'package:threateye/config/constants/api_constants.dart';
import 'package:threateye/core/network/interceptors/auth_interceptor.dart';

/// Factory for creating configured [Dio] instances.
///
/// Two variants are intentional:
///
/// * [createRawDio] — **no** [AuthInterceptor]. Used exclusively by
///   [AuthRemoteDataSourceImpl] so that login/refresh calls never re-enter
///   the interceptor and cause a circular refresh loop.
///
/// * [createDio] — adds [AuthInterceptor] for automatic token injection and
///   transparent 401-refresh on every other API call.
///
/// **Phase 6 — Production Hardening:**
/// - In release mode the base URL is forced to `https://` to prevent
///   accidental plaintext connections.
/// - An [IOHttpClientAdapter] is installed that validates the server's
///   TLS certificate against [_kPinnedSha256Fingerprints]. Any certificate
///   not in that set causes the connection to be rejected, preventing
///   Man-In-The-Middle (MITM) attacks.
/// - [LogInterceptor] is completely absent in release builds.
class DioFactory {
  DioFactory._();

  // ── Pinned SHA-256 certificate fingerprints (hex, lower-case, no colons) ───
  //
  // To obtain the fingerprint for your server:
  //   openssl s_client -connect <host>:<port> </dev/null 2>/dev/null \
  //     | openssl x509 -fingerprint -sha256 -noout \
  //     | sed 's/://g' | tr 'A-Z' 'a-z' | cut -d'=' -f2
  //
  // Add both the leaf certificate AND the intermediate CA fingerprint to
  // survive certificate rotation with a backup pin.
  //
  // TODO: Replace with your actual production certificate fingerprints before
  // submitting to the app stores.
  static const Set<String> _kPinnedSha256Fingerprints = {
    // ── Primary leaf certificate (replace before release) ──────────────────
    'aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899',
    // ── Backup / intermediate CA pin (replace before release) ──────────────
    '99887766554433221100ffeeddccbbaa99887766554433221100ffeeddccbbaa',
  };

  // ── Base-URL selection ─────────────────────────────────────────────────────

  /// Development uses the HTTP address from [ApiConstants].
  /// Release builds **require** HTTPS — any non-HTTPS base URL is upgraded.
  static String get _resolvedBaseUrl {
    if (!kReleaseMode) return ApiConstants.baseUrl;
    final raw = ApiConstants.baseUrl;
    if (raw.startsWith('https://')) return raw;
    return raw.replaceFirst('http://', 'https://');
  }

  // ── Shared base options ────────────────────────────────────────────────────

  static BaseOptions _baseOptions() => BaseOptions(
    baseUrl: _resolvedBaseUrl,
    connectTimeout: const Duration(milliseconds: ApiConstants.connectTimeoutMs),
    receiveTimeout: const Duration(milliseconds: ApiConstants.receiveTimeoutMs),
    sendTimeout: const Duration(milliseconds: ApiConstants.sendTimeoutMs),
    headers: {
      'Content-Type': ApiConstants.contentTypeJson,
      'Accept': ApiConstants.contentTypeJson,
    },
    responseType: ResponseType.json,
  );

  // ── Raw (no auth interceptor) ──────────────────────────────────────────────

  /// Returns a bare [Dio] with only the logging interceptor (debug) and the
  /// SSL-pinning adapter (release) attached.
  /// Used by [AuthRemoteDataSourceImpl] for login/refresh/logout calls.
  static Dio createRawDio() {
    final dio = Dio(_baseOptions());
    _applyHttpAdapter(dio);
    _addLogging(dio);
    return dio;
  }

  // ── Authenticated (with auth interceptor) ─────────────────────────────────

  /// Returns a [Dio] pre-wired with [authInterceptor].
  /// Used by [ApiClient] for all protected feature endpoints.
  ///
  /// **Important:** call [AuthInterceptor.init] with this Dio immediately
  /// after construction (see [injection_container.dart]) so the interceptor
  /// can retry failed requests.
  static Dio createDio({required AuthInterceptor authInterceptor}) {
    final dio = Dio(_baseOptions());
    dio.interceptors.add(authInterceptor);
    _applyHttpAdapter(dio);
    _addLogging(dio);
    return dio;
  }

  // ── SSL Pinning adapter ────────────────────────────────────────────────────

  /// Replaces the default [HttpClientAdapter] with a custom one that:
  ///
  /// - In **release** mode validates the server's certificate SHA-256
  ///   fingerprint against [_kPinnedSha256Fingerprints], rejecting any
  ///   certificate not in that set.
  /// - In **debug** mode performs no pinning so the dev server (plain HTTP
  ///   or a self-signed cert) is accepted without ceremony.
  static void _applyHttpAdapter(Dio dio) {
    if (!kReleaseMode) return; // no-op in debug / profile builds

    dio.httpClientAdapter = IOHttpClientAdapter(
      createHttpClient: () {
        final client = HttpClient();

        // Reject any certificate whose SHA-256 fingerprint is not pinned.
        client.badCertificateCallback =
            (X509Certificate cert, String host, int port) {
              // Returning `false` from badCertificateCallback REJECTS the cert.
              // We always return false because we validate inside
              // onHttpClientCreate / SecurityContext instead.
              return false;
            };

        return client;
      },
      validateCertificate: (X509Certificate? cert, String host, int port) {
        if (cert == null) return false;

        // Compute the SHA-256 fingerprint of the DER-encoded certificate.
        final fingerprint = sha256
            .convert(cert.der)
            .bytes
            .map((b) => b.toRadixString(16).padLeft(2, '0'))
            .join();

        return _kPinnedSha256Fingerprints.contains(fingerprint);
      },
    );
  }

  static void _addLogging(Dio dio) {
    if (kReleaseMode) return;

    dio.interceptors.add(
      LogInterceptor(
        request: true,
        requestHeader: true,
        requestBody: true,
        responseHeader: false,
        responseBody: true,
        error: true,
        logPrint: (object) => debugPrint(object.toString()),
      ),
    );
  }
}
