import 'package:flutter/material.dart';
import 'package:threateye/config/router/route_names.dart';
import 'package:threateye/config/theme/app_colors.dart';

class DashboardQuickResponse extends StatelessWidget {
  const DashboardQuickResponse({super.key});


  @override
  Widget build(BuildContext context) {
    final actions = [
      // Already wired — navigates to AlertsPage.
      _QuickAction(
        icon: Icons.manage_search_rounded,
        label: 'Investigate\nAlerts',
        color: AppColors.severityCritical,
        onTap: () => Navigator.pushNamed(context, RouteNames.alerts),
      ),
      // Sprint 2: wired to DecisionHistoryPage.
      _QuickAction(
        icon: Icons.history_rounded,
        label: 'Decision\nHistory',
        color: AppColors.severityHigh,
        onTap: () => Navigator.pushNamed(context, RouteNames.decisionHistory),
      ),
      // Sprint 2: wired to FirewallPage.
      _QuickAction(
        icon: Icons.radar_rounded,
        label: 'Security\nScan',
        color: AppColors.accent,
        onTap: () => Navigator.pushNamed(context, RouteNames.firewall),
      ),
    ];

    return Row(
      children: actions.map((a) {
        final isLast = actions.last == a;
        return Expanded(
          child: Padding(
            padding: EdgeInsets.only(right: isLast ? 0 : 8),
            child: _QuickActionButton(action: a),
          ),
        );
      }).toList(),
    );
  }
}

class _QuickAction {
  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback onTap;
  const _QuickAction({
    required this.icon,
    required this.label,
    required this.color,
    required this.onTap,
  });
}

class _QuickActionButton extends StatelessWidget {
  final _QuickAction action;
  const _QuickActionButton({required this.action});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: action.onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 14),
        decoration: BoxDecoration(
          color: action.color.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: action.color.withValues(alpha: 0.2)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(action.icon, color: action.color, size: 22),
            const SizedBox(height: 6),
            Text(
              action.label,
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w600,
                color: action.color,
                height: 1.3,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
