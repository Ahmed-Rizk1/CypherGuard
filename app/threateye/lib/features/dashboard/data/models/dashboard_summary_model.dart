import '../../domain/entities/dashboard_summary_entity.dart';

class DashboardSummaryModel extends DashboardSummaryEntity {
  const DashboardSummaryModel({
    required super.criticalAlerts,
    required super.highAlerts,
    required super.mediumAlerts,
    required super.lowAlerts,
    required super.newAlerts,
    required super.acknowledgedAlerts,
    required super.resolvedAlerts,
    required super.totalBlockedIps,
    required super.recentBlocks24h,
    required super.decisionsToday,
  });

  /// Deserializes from the SecureNet `/v1/mobile/dashboard/summary` response.
  ///
  /// Expected JSON structure:
  /// ```json
  /// {
  ///   "alerts_by_severity": { "critical": 5, "high": 12, "medium": 34, "low": 89 },
  ///   "alerts_by_status":   { "new": 15, "acknowledged": 8, "resolved": 102 },
  ///   "total_blocked_ips":  23,
  ///   "recent_blocks_24h":  7,
  ///   "decisions_today":    12
  /// }
  /// ```
  factory DashboardSummaryModel.fromJson(Map<String, dynamic> json) {
    final severity = (json['alerts_by_severity'] as Map<String, dynamic>?) ?? {};
    final status   = (json['alerts_by_status']   as Map<String, dynamic>?) ?? {};

    return DashboardSummaryModel(
      criticalAlerts:     (severity['critical']    as num?)?.toInt() ?? 0,
      highAlerts:         (severity['high']        as num?)?.toInt() ?? 0,
      mediumAlerts:       (severity['medium']      as num?)?.toInt() ?? 0,
      lowAlerts:          (severity['low']         as num?)?.toInt() ?? 0,
      newAlerts:          (status['new']           as num?)?.toInt() ?? 0,
      acknowledgedAlerts: (status['acknowledged']  as num?)?.toInt() ?? 0,
      resolvedAlerts:     (status['resolved']      as num?)?.toInt() ?? 0,
      totalBlockedIps:    (json['total_blocked_ips']  as num?)?.toInt() ?? 0,
      recentBlocks24h:    (json['recent_blocks_24h']  as num?)?.toInt() ?? 0,
      decisionsToday:     (json['decisions_today']    as num?)?.toInt() ?? 0,
    );
  }

  /// Mock data for UI development / offline testing.
  factory DashboardSummaryModel.mock() {
    return const DashboardSummaryModel(
      criticalAlerts:     5,
      highAlerts:         12,
      mediumAlerts:       34,
      lowAlerts:          89,
      newAlerts:          15,
      acknowledgedAlerts: 8,
      resolvedAlerts:     102,
      totalBlockedIps:    23,
      recentBlocks24h:    7,
      decisionsToday:     12,
    );
  }
}

