import 'package:flutter/material.dart';
import 'package:threateye/config/theme/app_colors.dart';
import 'package:threateye/features/dashboard/domain/entities/dashboard_summary_entity.dart';

class DashboardStatsGrid extends StatelessWidget {
  final DashboardSummaryEntity summary;

  const DashboardStatsGrid({super.key, required this.summary});

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.of(context).size;
    final width = size.width;

    // Responsive sizing
    final isSmallPhone = width < 360;
    final isTablet = width >= 700;

    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: 4,

      gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: isTablet ? 4 : 2,
        crossAxisSpacing: isSmallPhone ? 10 : 14,
        mainAxisSpacing: isSmallPhone ? 10 : 14,

        // Dynamic ratio for all screens
        childAspectRatio: isTablet
            ? 1.35
            : isSmallPhone
            ? 0.92
            : 1.05,
      ),

      itemBuilder: (context, index) {
        final items = [
          (
            label: 'Total Threats',
            value: '${summary.totalAlerts}',
            icon: Icons.bug_report_rounded,
            color: AppColors.primary,
            sub: 'All severity levels',
          ),
          (
            label: 'Critical Alerts',
            value: '${summary.criticalAlerts}',
            icon: Icons.warning_amber_rounded,
            color: AppColors.severityCritical,
            sub: 'Immediate action',
          ),
          (
            label: 'Active Incidents',
            value: '${summary.activeIncidents}',
            icon: Icons.local_fire_department_rounded,
            color: AppColors.severityHigh,
            sub: 'Under investigation',
          ),
          (
            label: 'IPs Blocked',
            value: '${summary.totalBlockedIps}',
            icon: Icons.block_rounded,
            color: AppColors.accent,
            sub: '+${summary.recentBlocks24h} last 24h',
          ),
        ];

        final item = items[index];

        return _StatCard(
          label: item.label,
          value: item.value,
          icon: item.icon,
          accentColor: item.color,
          subLabel: item.sub,
          isSmallPhone: isSmallPhone,
          isTablet: isTablet,
        );
      },
    );
  }
}

class _StatCard extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;
  final Color accentColor;
  final String subLabel;
  final bool isSmallPhone;
  final bool isTablet;

  const _StatCard({
    required this.label,
    required this.value,
    required this.icon,
    required this.accentColor,
    required this.subLabel,
    required this.isSmallPhone,
    required this.isTablet,
  });

  @override
  Widget build(BuildContext context) {
    final horizontalPadding = isSmallPhone ? 12.0 : 16.0;
    final verticalPadding = isSmallPhone ? 12.0 : 16.0;

    final iconSize = isSmallPhone ? 18.0 : 20.0;
    final numberSize = isTablet
        ? 34.0
        : isSmallPhone
        ? 24.0
        : 30.0;

    final titleSize = isSmallPhone ? 12.0 : 13.5;
    final subtitleSize = isSmallPhone ? 10.0 : 11.5;

    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: horizontalPadding,
        vertical: verticalPadding,
      ),
      decoration: BoxDecoration(
        color: AppColors.backgroundCard,
        borderRadius: BorderRadius.circular(isSmallPhone ? 16 : 20),
        border: Border.all(color: AppColors.borderDefault),
        boxShadow: [
          BoxShadow(
            color: accentColor.withValues(alpha: 0.08),
            blurRadius: 18,
            offset: const Offset(0, 6),
          ),
        ],
      ),

      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Top Row: icon + pulse dot ──────────────────────────────────────
          Row(
            children: [
              Container(
                padding: EdgeInsets.all(isSmallPhone ? 8 : 10),
                decoration: BoxDecoration(
                  color: accentColor.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(icon, color: accentColor, size: iconSize),
              ),
              const Spacer(),
              Container(
                width: 8,
                height: 8,
                decoration: BoxDecoration(
                  color: accentColor,
                  shape: BoxShape.circle,
                ),
              ),
            ],
          ),

          // ── Flexible gap: absorbs surplus height, never overflows ──────────
          const Spacer(),

          // ── Main metric value ─────────────────────────────────────────────
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Text(
              value,
              maxLines: 1,
              style: TextStyle(
                fontSize: numberSize,
                height: 1,
                fontWeight: FontWeight.w800,
                color: accentColor,
                letterSpacing: -1,
              ),
            ),
          ),

          SizedBox(height: isSmallPhone ? 6 : 8),

          // ── Label ─────────────────────────────────────────────────────────
          Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              fontSize: titleSize,
              fontWeight: FontWeight.w700,
              color: AppColors.textPrimary,
              height: 1.2,
            ),
          ),

          SizedBox(height: isSmallPhone ? 3 : 4),

          Text(
            subLabel,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              fontSize: subtitleSize,
              height: 1.2,
              color: AppColors.textSecondary,
            ),
          ),
        ],
      ),
    );
  }
}
