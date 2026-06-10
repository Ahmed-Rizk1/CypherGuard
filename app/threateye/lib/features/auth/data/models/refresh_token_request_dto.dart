/// Data Transfer Object for the token-refresh endpoint.
///
/// Sent as the JSON body to `POST /v1/mobile/auth/refresh`:
/// ```json
/// { "refresh_token": "eyJhbG..." }
/// ```
class RefreshTokenRequestDto {
  final String refreshToken;

  const RefreshTokenRequestDto({required this.refreshToken});

  Map<String, dynamic> toJson() => {'refresh_token': refreshToken};
}
