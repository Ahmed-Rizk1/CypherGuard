import 'package:flutter/material.dart';


import '../../config/theme/app_spacing.dart';
import '../../config/theme/app_text_styles.dart';
import '../utils/app_enums.dart';
import '../utils/extensions.dart';

/// Severity/status chip for alert cards and detail views.
class StatusChip extends StatelessWidget {
  final AlertSeverity severity;

  const StatusChip({super.key, required this.severity});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.sm,
        vertical: AppSpacing.xs,
      ),
      decoration: BoxDecoration(
        color: severity.backgroundColor,
        borderRadius: BorderRadius.circular(AppSpacing.radiusFull),
        border: Border.all(color: severity.color.withOpacity(0.4)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(
              color: severity.color,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 5),
          Text(
            severity.label,
            style: AppTextStyles.labelSmall.copyWith(
              color: severity.color,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}