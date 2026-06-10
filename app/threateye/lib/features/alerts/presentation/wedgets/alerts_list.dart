import 'package:flutter/material.dart';
import '../../domain/entities/attack_alert_entity.dart';
import 'alert_card.dart';
import 'alert_severity_utils.dart';
import 'severity_bar.dart';
import 'summary_chip.dart';

class AlertsList extends StatelessWidget {
  final List<AttackAlertEntity> alerts;

  /// Optional external [ScrollController] for pagination scroll detection.
  final ScrollController? scrollController;

  /// Optional widget rendered at the very bottom of the list
  /// (e.g., a load-more spinner or end-of-list indicator).
  final Widget? footer;

  const AlertsList({
    super.key,
    required this.alerts,
    this.scrollController,
    this.footer,
  });

  @override
  Widget build(BuildContext context) {
    final criticalCount =
        alerts.where((a) => a.severity.toLowerCase() == 'critical').length;
    final highCount =
        alerts.where((a) => a.severity.toLowerCase() == 'high').length;
    final mediumCount =
        alerts.where((a) => a.severity.toLowerCase() == 'medium').length;
    final lowCount = alerts
        .where((a) =>
            !['critical', 'high', 'medium'].contains(a.severity.toLowerCase()))
        .length;

    return CustomScrollView(
      controller: scrollController,
      slivers: [
        // ── Summary header ──────────────────────────────────────
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(14, 36, 14, 4),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SizedBox(height: 8),
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.red.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(
                            color: Colors.red.withValues(alpha: 0.25)),
                      ),
                      child: Row(
                        children: [
                          Container(
                            width: 7,
                            height: 7,
                            decoration: const BoxDecoration(
                              color: Colors.red,
                              shape: BoxShape.circle,
                            ),
                          ),
                          const SizedBox(width: 6),
                          Text(
                            '${alerts.length} total',
                            style: const TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w700,
                              color: Colors.red,
                              decoration: TextDecoration.none,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                // Severity summary chips
                Row(
                  children: [
                    SummaryChip(
                      label: 'Critical',
                      count: criticalCount,
                      color: const Color(0xFFEF4444),
                    ),
                    const SizedBox(width: 8),
                    SummaryChip(
                      label: 'High',
                      count: highCount,
                      color: const Color(0xFFF97316),
                    ),
                    const SizedBox(width: 8),
                    SummaryChip(
                      label: 'Medium',
                      count: mediumCount,
                      color: const Color(0xFFF59E0B),
                    ),
                    const SizedBox(width: 8),
                  ],
                ),
                const SizedBox(height: 14),
                // Severity progress bar
                SeverityBar(
                  total: alerts.length,
                  critical: criticalCount,
                  high: highCount,
                  medium: mediumCount,
                  low: lowCount,
                ),
                const SizedBox(height: 18),
              ],
            ),
          ),
        ),

        // ── Alert cards ─────────────────────────────────────────
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(14, 0, 14, 24),
          sliver: SliverList(
            delegate: SliverChildBuilderDelegate(
              (context, index) {
                final alert = alerts[index];
                return AlertCard(
                  alert: alert,
                  color: AlertSeverityUtils.severityColor(alert.severity),
                  icon: AlertSeverityUtils.severityIcon(alert.severity),
                );
              },
              childCount: alerts.length,
            ),
          ),
        ),

        // ── Optional footer (load-more spinner / end-of-list) ────
        if (footer != null)
          SliverToBoxAdapter(child: footer!),
      ],
    );
  }
}
