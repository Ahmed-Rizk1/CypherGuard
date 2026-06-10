/// Represents the `data` object inside the login API response.
///
/// Example API response:
/// ```json
/// {
///   "success": true,
///   "data": {
///     "access_token": "eyJhbG...",
///     "refresh_token": "eyJhbG...",
///     "token_type": "bearer",
///     "expires_in": 1800,
///     "role": "analyst"
///   }
/// }
/// ```
class AuthResponseModel {
  final String accessToken;
  final String refreshToken;
  final String tokenType;
  final int expiresIn;
  final String role;

  const AuthResponseModel({
    required this.accessToken,
    required this.refreshToken,
    required this.tokenType,
    required this.expiresIn,
    required this.role,
  });

  factory AuthResponseModel.fromJson(Map<String, dynamic> json) {
    final data = json['data'] as Map<String, dynamic>? ?? json;
    return AuthResponseModel(
      accessToken:  data['access_token']  as String? ?? '',
      refreshToken: data['refresh_token'] as String? ?? '',
      tokenType:    data['token_type']    as String? ?? 'bearer',
      expiresIn:    (data['expires_in']   as num?)?.toInt() ?? 0,
      role:         data['role']          as String? ?? 'analyst',
    );
  }
}
