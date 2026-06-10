/// Domain entity that mirrors the SecureNet `/v1/mobile/dashboard/summary` response.
///
/// The API returns:
/// ```json
/// {
///   "alerts_by_severity": { "critical": 5, "high": 12, "medium": 34, "low": 89 },
///   "alerts_by_status":   { "new": 15, "acknowledged": 8, "resolved": 102 },
///   "total_blocked_ips":  23,
///   "recent_blocks_24h":  7,
///   "decisions_today":    12
/// }
/// ```
class DashboardSummaryEntity {
  final int criticalAlerts;
  final int highAlerts;
  final int mediumAlerts;
  final int lowAlerts;

  final int newAlerts;
  final int acknowledgedAlerts;
  final int resolvedAlerts;

  final int totalBlockedIps;
  final int recentBlocks24h;
  final int decisionsToday;

  const DashboardSummaryEntity({
    required this.criticalAlerts,
    required this.highAlerts,
    required this.mediumAlerts,
    required this.lowAlerts,
    required this.newAlerts,
    required this.acknowledgedAlerts,
    required this.resolvedAlerts,
    required this.totalBlockedIps,
    required this.recentBlocks24h,
    required this.decisionsToday,
  });

  int get totalAlerts => criticalAlerts + highAlerts + mediumAlerts + lowAlerts;

  int get activeIncidents => newAlerts + acknowledgedAlerts;

  String get systemStatus => criticalAlerts > 0 ? 'Warning' : 'Normal';
}
