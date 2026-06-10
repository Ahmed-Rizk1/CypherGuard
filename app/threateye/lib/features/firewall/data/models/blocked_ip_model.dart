import '../../domain/entities/blocked_ip_entity.dart';

/// Data-layer model for a blocked IP entry.
///
/// Extends [BlockedIpEntity] so it IS-A entity (same pattern as
/// [AttackAlertModel] and [DecisionModel]).
class BlockedIpModel extends BlockedIpEntity {
  const BlockedIpModel({
    required super.id,
    required super.ipAddress,
    required super.reason,
    required super.blockedAt,
    super.blockedBy,
    super.expiresAt,
  });

  /// Deserialises from the SecureNet API response.
  ///
  /// Expected JSON shape:
  /// ```json
  /// {
  ///   "id":         "fw-001",
  ///   "ip_address": "192.168.1.100",
  ///   "reason":     "DDoS source",
  ///   "blocked_at": "2025-05-17T12:00:00Z",
  ///   "blocked_by": "soc-analyst-2",
  ///   "expires_at": null
  /// }
  /// ```
  factory BlockedIpModel.fromJson(Map<String, dynamic> json) {
    return BlockedIpModel(
      id:        json['id']?.toString()         ?? '',
      ipAddress: json['ip_address']?.toString() ?? '',
      reason:    json['reason']   as String?    ?? '',
      blockedAt: json['blocked_at']             ?? json['created_at'] ?? '',
      blockedBy: json['blocked_by'] as String?,
      expiresAt: json['expires_at'] as String?,
    );
  }

  /// Serialises to JSON (for local operations or debugging).
  Map<String, dynamic> toJson() => {
    'id':         id,
    'ip_address': ipAddress,
    'reason':     reason,
    'blocked_at': blockedAt,
    if (blockedBy != null) 'blocked_by': blockedBy,
    if (expiresAt != null) 'expires_at': expiresAt,
  };
}
