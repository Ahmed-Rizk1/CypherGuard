import 'package:threateye/core/error/exceptions.dart';
import 'package:threateye/core/network/api_client.dart';
import 'package:threateye/core/network/endpoints.dart';
import 'package:threateye/core/network/paginated_response.dart';
import '../models/attack_alert_model.dart';

abstract class AlertsRemoteDataSource {
  /// `GET /v1/mobile/alerts?per_page=20[&severity=x][&status=y][&cursor=z]`
  Future<PaginatedResponse<AttackAlertModel>> getAlerts({
    String? severity,
    String? status,
    String? cursor,
  });

  /// `GET /v1/mobile/alerts/{id}`
  Future<AttackAlertModel> getAlertById(String id);

  /// `PATCH /v1/mobile/alerts/{id}` with body `{"status": newStatus}`.
  Future<AttackAlertModel> updateAlertStatus(String id, String newStatus);
}

// ── Implementation ─────────────────────────────────────────────────────────

class AlertsRemoteDataSourceImpl implements AlertsRemoteDataSource {
  final ApiClient _client;

  const AlertsRemoteDataSourceImpl(this._client);

  // ── getAlerts ──────────────────────────────────────────────────────────────

  @override
  Future<PaginatedResponse<AttackAlertModel>> getAlerts({
    String? severity,
    String? status,
    String? cursor,
  }) async {
    final queryParams = <String, dynamic>{
      'per_page': 20,
      if (severity != null && severity.isNotEmpty) 'severity': severity,
      if (status   != null && status.isNotEmpty)   'status':   status,
      if (cursor   != null && cursor.isNotEmpty)   'cursor':   cursor,
    };

    final response = await _client.get(
      Endpoints.alerts,
      queryParameters: queryParams,
    );

    final body = response.data as Map<String, dynamic>;
    _assertSuccess(body, 'Failed to load alerts.');

    return PaginatedResponse.fromJson(body, AttackAlertModel.fromJson);
  }

  // ── getAlertById ───────────────────────────────────────────────────────────

  @override
  Future<AttackAlertModel> getAlertById(String id) async {
    final response = await _client.get(Endpoints.alertById(id));

    final body = response.data as Map<String, dynamic>;
    _assertSuccess(body, 'Failed to load alert.');

    final data = body['data'] as Map<String, dynamic>? ?? body;
    return AttackAlertModel.fromJson(data);
  }

  // ── updateAlertStatus ──────────────────────────────────────────────────────

  @override
  Future<AttackAlertModel> updateAlertStatus(
    String id,
    String newStatus,
  ) async {
    final response = await _client.patch(
      Endpoints.alertById(id),
      data: {'status': newStatus},
    );

    final body = response.data as Map<String, dynamic>;
    _assertSuccess(body, 'Failed to update alert status.');

    final data = body['data'] as Map<String, dynamic>? ?? body;
    return AttackAlertModel.fromJson(data);
  }

  // ── helpers ────────────────────────────────────────────────────────────────

  /// Throws a [ServerException] if the API envelope signals a failure.
  void _assertSuccess(Map<String, dynamic> body, String fallbackMessage) {
    if (body['success'] == false) {
      final err = body['error'] as Map<String, dynamic>?;
      throw ServerException(
        message: err?['message'] as String? ?? fallbackMessage,
        errorCode: err?['code'] as String?,
      );
    }
  }
}
