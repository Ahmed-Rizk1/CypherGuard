import 'package:flutter/material.dart';
import 'detail_section_label.dart';
import 'quick_action_button.dart';

class AlertQuickActions extends StatelessWidget {
  /// Null callbacks mean the button is disabled (PATCH in-flight).
  final VoidCallback? onMarkResolved;
  final VoidCallback? onEscalate;
  final VoidCallback? onIgnore;

  /// When `true`, all buttons are replaced by a loading indicator.
  /// This enforces the UI State Protection constraint — no duplicate submissions.
  final bool isLoading;

  const AlertQuickActions({
    super.key,
    required this.onMarkResolved,
    required this.onEscalate,
    required this.onIgnore,
    this.isLoading = false,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const DetailSectionLabel(
          icon: Icons.touch_app_rounded,
          title: 'Analyst Quick Actions',
        ),
        if (isLoading)
          // ── UI State Protection: spinner replaces buttons during PATCH ──
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 12),
            child: Center(
              child: SizedBox(
                width:  28,
                height: 28,
                child:  CircularProgressIndicator(strokeWidth: 2.5),
              ),
            ),
          )
        else
          Row(
            children: [
              Expanded(
                child: QuickActionButton(
                  label: 'Mark Resolved',
                  icon:  Icons.check_circle_rounded,
                  color: const Color(0xFF22C55E),
                  onTap: onMarkResolved,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: QuickActionButton(
                  label: 'Escalate',
                  icon:  Icons.arrow_circle_up_rounded,
                  color: const Color(0xFFF97316),
                  onTap: onEscalate,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: QuickActionButton(
                  label: 'Ignore',
                  icon:  Icons.do_not_disturb_rounded,
                  color: Colors.blueGrey,
                  onTap: onIgnore,
                ),
              ),
            ],
          ),
      ],
    );
  }
}
