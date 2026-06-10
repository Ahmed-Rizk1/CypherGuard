import 'package:threateye/core/error/exceptions.dart';
import 'package:threateye/core/network/api_client.dart';
import 'package:threateye/core/network/endpoints.dart';
import 'package:threateye/core/network/paginated_response.dart';
import '../models/blocked_ip_model.dart';

// ── Abstract contract ───────────────────────────────────────────────────────

abstract class FirewallRemoteDataSource {
  /// `GET /v1/mobile/firewall?per_page=20[&cursor=z]`
  Future<PaginatedResponse<BlockedIpModel>> getBlockedIps({String? cursor});

  /// `POST /v1/mobile/firewall/block`
  ///
  /// Body: `{"ip_address": ipAddress, "reason": reason}`
  Future<BlockedIpModel> blockIp({
    required String ipAddress,
    required String reason,
  });

  /// `DELETE /v1/mobile/firewall/block/{ip}`
  ///
  /// Returns `true` on success (API returns 200 / 204 with no body).
  Future<void> unblockIp(String ipAddress);
}

// ── Implementation ──────────────────────────────────────────────────────────

class FirewallRemoteDataSourceImpl implements FirewallRemoteDataSource {
  final ApiClient _client;

  const FirewallRemoteDataSourceImpl(this._client);

  // ── getBlockedIps ──────────────────────────────────────────────────────────

  @override
  Future<PaginatedResponse<BlockedIpModel>> getBlockedIps({
    String? cursor,
  }) async {
    final queryParams = <String, dynamic>{
      'per_page': 20,
      if (cursor != null && cursor.isNotEmpty) 'cursor': cursor,
    };

    final response = await _client.get(
      Endpoints.firewall,
      queryParameters: queryParams,
    );

    final body = response.data as Map<String, dynamic>;
    _assertSuccess(body, 'Failed to load blocked IPs.');

    return PaginatedResponse.fromJson(body, BlockedIpModel.fromJson);
  }

  // ── blockIp ────────────────────────────────────────────────────────────────

  @override
  Future<BlockedIpModel> blockIp({
    required String ipAddress,
    required String reason,
  }) async {
    final response = await _client.post(
      Endpoints.firewallBlock,
      data: {
        'ip_address': ipAddress,
        'reason':     reason,
      },
    );

    final body = response.data as Map<String, dynamic>;
    _assertSuccess(body, 'Failed to block IP address.');

    final data = body['data'] as Map<String, dynamic>? ?? body;
    return BlockedIpModel.fromJson(data);
  }

  // ── unblockIp ──────────────────────────────────────────────────────────────

  @override
  Future<void> unblockIp(String ipAddress) async {
    final response = await _client.delete(
      Endpoints.firewallUnblock(ipAddress),
    );

    // Some APIs return 204 No Content — handle gracefully.
    final statusCode = response.statusCode ?? 200;
    if (statusCode >= 400) {
      final body = response.data;
      final message = (body is Map)
          ? (body['error']?['message'] as String? ?? 'Failed to unblock IP.')
          : 'Failed to unblock IP.';
      throw ServerException(message: message, statusCode: statusCode);
    }
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
