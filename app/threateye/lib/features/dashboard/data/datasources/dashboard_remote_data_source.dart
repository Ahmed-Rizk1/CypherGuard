import 'package:threateye/core/error/exceptions.dart';
import 'package:threateye/core/network/api_client.dart';
import 'package:threateye/core/network/endpoints.dart';
import '../models/dashboard_summary_model.dart';

// ── Abstract contract ──────────────────────────────────────────────────────

abstract class DashboardRemoteDataSource {
  /// Fetches the dashboard summary from `GET /v1/mobile/dashboard/summary`.
  ///
  /// Throws an [AppException] sub-class on any failure; callers should catch
  /// and map to a [Failure].
  Future<DashboardSummaryModel> getDashboardSummary();
}

// ── Implementation ─────────────────────────────────────────────────────────

class DashboardRemoteDataSourceImpl implements DashboardRemoteDataSource {
  final ApiClient _client;

  const DashboardRemoteDataSourceImpl(this._client);

  @override
  Future<DashboardSummaryModel> getDashboardSummary() async {
    final response = await _client.get(Endpoints.dashboardSummary);

    final body = response.data as Map<String, dynamic>;

    // Standard SecureNet envelope: { "success": true, "data": { ... } }
    if (body['success'] == false) {
      final err = body['error'] as Map<String, dynamic>?;
      throw ServerException(
        message:   err?['message'] as String? ?? 'Failed to load dashboard.',
        errorCode: err?['code']    as String?,
      );
    }

    final data = body['data'] as Map<String, dynamic>? ?? body;
    return DashboardSummaryModel.fromJson(data);
  }
}
