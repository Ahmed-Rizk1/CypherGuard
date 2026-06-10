import 'package:flutter/material.dart';
import 'package:threateye/config/theme/app_colors.dart';

class DashboardSectionLabel extends StatelessWidget {
  final String label;
  final IconData icon;
  final String? trailingLabel;
  final Color? trailingColor;

  const DashboardSectionLabel({
    super.key,
    required this.label,
    required this.icon,
    this.trailingLabel,
    this.trailingColor,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, size: 16, color: AppColors.primaryLight),
        const SizedBox(width: 8),
        Text(
          label,
          style: const TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w700,
            color: AppColors.textPrimary,
            letterSpacing: 0.3,
          ),
        ),
        if (trailingLabel != null) ...[
          const Spacer(),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(
              color: (trailingColor ?? AppColors.primary).withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Text(
              trailingLabel!,
              style: TextStyle(
                fontSize: 9,
                fontWeight: FontWeight.w800,
                color: trailingColor ?? AppColors.primary,
                letterSpacing: 1.2,
              ),
            ),
          ),
        ],
      ],
    );
  }
}
