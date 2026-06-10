import 'package:flutter/material.dart';
import 'package:threateye/config/theme/app_colors.dart';

class DashboardSecurityStatus extends StatelessWidget {
  const DashboardSecurityStatus({super.key});

  static const _statuses = [
    _StatusItem(
      label: 'Firewall',
      sub: 'Active',
      icon: Icons.fireplace_rounded,
      color: AppColors.statusSuccess,
    ),
    _StatusItem(
      label: 'Endpoint Protection',
      sub: 'Secure',
      icon: Icons.devices_rounded,
      color: AppColors.statusSuccess,
    ),
    _StatusItem(
      label: 'Network Traffic',
      sub: 'Monitored',
      icon: Icons.network_check_rounded,
      color: AppColors.statusWarning,
    ),
    _StatusItem(
      label: 'Threat Intelligence',
      sub: 'Online',
      icon: Icons.psychology_rounded,
      color: AppColors.statusSuccess,
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.backgroundCard,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.borderDefault),
      ),
      child: Column(
        children: _statuses.map((s) {
          final isLast = _statuses.last == s;
          return Column(
            children: [
              _StatusTile(item: s),
              if (!isLast)
                const Divider(
                  height: 1,
                  color: AppColors.divider,
                  indent: 16,
                  endIndent: 16,
                ),
            ],
          );
        }).toList(),
      ),
    );
  }
}

class _StatusItem {
  final String label;
  final String sub;
  final IconData icon;
  final Color color;
  const _StatusItem({
    required this.label,
    required this.sub,
    required this.icon,
    required this.color,
  });
}

class _StatusTile extends StatelessWidget {
  final _StatusItem item;
  const _StatusTile({required this.item});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      child: Row(
        children: [
          Container(
            width: 34,
            height: 34,
            decoration: BoxDecoration(
              color: item.color.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(item.icon, color: item.color, size: 18),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              item.label,
              style: const TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w500,
                color: AppColors.textPrimary,
              ),
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: item.color.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 5,
                  height: 5,
                  decoration: BoxDecoration(
                    color: item.color,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 5),
                Text(
                  item.sub,
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: item.color,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
