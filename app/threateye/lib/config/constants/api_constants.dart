/// API-related constants for the SecureNet Mobile Gateway.
class ApiConstants {
  ApiConstants._();

  // ── Base URL ───────────────────────────────────────────────────────────────
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://16.171.61.103:8005',
  );

  // ── Timeouts (ms) ─────────────────────────────────────────────────────────
  static const int connectTimeoutMs = 15000;
  static const int receiveTimeoutMs = 15000;
  static const int sendTimeoutMs    = 15000;

  // ── Header keys ───────────────────────────────────────────────────────────
  static const String authHeader      = 'Authorization';
  static const String bearerPrefix    = 'Bearer';
  static const String contentTypeJson = 'application/json';

  // ── Secure storage keys ───────────────────────────────────────────────────
  static const String accessTokenKey  = 'access_token';
  static const String refreshTokenKey = 'refresh_token';
  static const String userRoleKey     = 'user_role';

  // ── API version ───────────────────────────────────────────────────────────
  static const String apiVersion = 'v1';

  // ── API error codes (from `error.code` in the response envelope) ──────────
  /// Credentials are wrong — show "invalid email or password".
  static const String errAuthInvalid = 'AUTH_INVALID';

  /// Access token has expired — the interceptor should refresh automatically.
  /// If seen in the Cubit it means the refresh itself failed.
  static const String errAuthTokenExpired = 'AUTH_TOKEN_EXPIRED';

  /// Too many login attempts — user must wait 60 seconds.
  static const String errRateLimited = 'RATE_LIMITED';

  /// Account locked after 5+ failures — user must wait 15 minutes.
  static const String errAccountLocked = 'ACCOUNT_LOCKED';
}