import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../domain/entities/attack_alert_entity.dart';
import 'detail_section_label.dart';

class AlertDetailsCard extends StatelessWidget {
  final AttackAlertEntity alert;
  final Color severityColor;
  final void Function(String message, Color color, IconData icon) onShowSnackBar;

  const AlertDetailsCard({
    super.key,
    required this.alert,
    required this.severityColor,
    required this.onShowSnackBar,
  });

  @override
  Widget build(BuildContext context) {
    final rows = [
      {'icon': Icons.security_rounded, 'label': 'Attack Type', 'value': alert.attackType},
      {'icon': Icons.access_time_rounded, 'label': 'Detected At', 'value': alert.time},
      {'icon': Icons.language_rounded, 'label': 'Source IP', 'value': alert.sourceIp},
      {'icon': Icons.fingerprint_rounded, 'label': 'Alert ID', 'value': alert.id},
      {'icon': Icons.info_outline_rounded, 'label': 'Status', 'value': alert.status},
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const DetailSectionLabel(icon: Icons.list_alt_rounded, title: 'Alert Details'),
        Card(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
          child: Column(
            children: List.generate(rows.length, (i) {
              final row = rows[i];
              final isLast = i == rows.length - 1;
              return Column(
                children: [
                  InkWell(
                    onLongPress: () {
                      Clipboard.setData(ClipboardData(text: row['value'] as String));
                      onShowSnackBar(
                        'Copied to clipboard',
                        Colors.blueGrey,
                        Icons.copy_rounded,
                      );
                    },
                    borderRadius: BorderRadius.vertical(
                      top: i == 0 ? const Radius.circular(14) : Radius.zero,
                      bottom: isLast ? const Radius.circular(14) : Radius.zero,
                    ),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                      child: Row(
                        children: [
                          Container(
                            width: 34,
                            height: 34,
                            decoration: BoxDecoration(
                              color: severityColor.withValues(alpha: 0.08),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Icon(
                              row['icon'] as IconData,
                              size: 17,
                              color: severityColor.withValues(alpha: 0.8),
                            ),
                          ),
                          const SizedBox(width: 14),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  row['label'] as String,
                                  style: TextStyle(
                                    fontSize: 11,
                                    color: Colors.grey.shade500,
                                  ),
                                ),
                                const SizedBox(height: 3),
                                Text(
                                  row['value'] as String,
                                  style: const TextStyle(
                                    fontSize: 14,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          Icon(Icons.copy_rounded, size: 14, color: Colors.grey.shade400),
                        ],
                      ),
                    ),
                  ),
                  if (!isLast) const Divider(height: 1, indent: 16, endIndent: 16),
                ],
              );
            }),
          ),
        ),
      ],
    );
  }
}
