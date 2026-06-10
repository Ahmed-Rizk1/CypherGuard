import 'package:threateye/core/error/exceptions.dart';
import 'package:threateye/core/network/api_client.dart';
import 'package:threateye/core/network/endpoints.dart';
import 'package:threateye/core/network/paginated_response.dart';
import '../models/decision_model.dart';

// ── Abstract contract ───────────────────────────────────────────────────────

abstract class DecisionRemoteDataSource {
  /// `POST /v1/mobile/decision`
  ///
  /// Body: `{"alert_id": alertId, "action": "APPROVE|REJECT|ESCALATE"}`
  Future<DecisionModel> submitDecision({
    required String alertId,
    required String action,
    String? note,
  });

  /// `GET /v1/mobile/decisions?per_page=20[&cursor=z]`
  Future<PaginatedResponse<DecisionModel>> getDecisionHistory({
    String? cursor,
  });
}

// ── Implementation ──────────────────────────────────────────────────────────

class DecisionRemoteDataSourceImpl implements DecisionRemoteDataSource {
  final ApiClient _client;

  const DecisionRemoteDataSourceImpl(this._client);

  // ── submitDecision ─────────────────────────────────────────────────────────

  @override
  Future<DecisionModel> submitDecision({
    required String alertId,
    required String action,
    String? note,
  }) async {
    final payload = <String, dynamic>{
      'alert_id': alertId,
      'action':   action,
      if (note != null && note.isNotEmpty) 'note': note,
    };

    final response = await _client.post(
      Endpoints.submitDecision,
      data: payload,
    );

    final body = response.data as Map<String, dynamic>;
    _assertSuccess(body, 'Failed to submit decision.');

    final data = body['data'] as Map<String, dynamic>? ?? body;
    return DecisionModel.fromJson(data);
  }

  // ── getDecisionHistory ─────────────────────────────────────────────────────

  @override
  Future<PaginatedResponse<DecisionModel>> getDecisionHistory({
    String? cursor,
  }) async {
    final queryParams = <String, dynamic>{
      'per_page': 20,
      if (cursor != null && cursor.isNotEmpty) 'cursor': cursor,
    };

    final response = await _client.get(
      Endpoints.decisions,
      queryParameters: queryParams,
    );

    final body = response.data as Map<String, dynamic>;
    _assertSuccess(body, 'Failed to load decision history.');

    return PaginatedResponse.fromJson(body, DecisionModel.fromJson);
  }

  // ── private helper ─────────────────────────────────────────────────────────

  void _assertSuccess(Map<String, dynamic> body, String fallback) {
    if (body['success'] == false) {
      final err = body['error'] as Map<String, dynamic>?;
      throw ServerException(
        message:   err?['message'] as String? ?? fallback,
        errorCode: err?['code']    as String?,
      );
    }
  }
}
