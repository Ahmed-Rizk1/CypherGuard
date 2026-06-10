import 'package:flutter/material.dart';
import 'alert_severity_utils.dart';
import 'detail_section_label.dart';

class RecommendedResponseCard extends StatelessWidget {
  final String attackType;

  const RecommendedResponseCard({super.key, required this.attackType});

  @override
  Widget build(BuildContext context) {
    final actions = AlertSeverityUtils.responseActions(attackType);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const DetailSectionLabel(icon: Icons.shield_rounded, title: 'Recommended Response'),
        Card(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
          child: ListView.separated(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: actions.length,
            separatorBuilder: (_, __) =>
                const Divider(height: 1, indent: 62, endIndent: 16),
            itemBuilder: (context, index) {
              final action = actions[index];
              return Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                child: Row(
                  children: [
                    Container(
                      width: 38,
                      height: 38,
                      decoration: BoxDecoration(
                        color: Colors.blueAccent.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Icon(
                        action['icon'] as IconData,
                        size: 19,
                        color: Colors.blueAccent,
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Text(
                        action['label'] as String,
                        style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                    const Icon(Icons.chevron_right_rounded, size: 18, color: Colors.grey),
                  ],
                ),
              );
            },
          ),
        ),
      ],
    );
  }
}
