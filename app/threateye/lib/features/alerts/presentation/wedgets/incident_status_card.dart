import 'package:flutter/material.dart';
import 'alert_severity_utils.dart';
import 'detail_section_label.dart';

class IncidentStatusCard extends StatelessWidget {
  final String incidentStatus;
  final ValueChanged<String> onStatusChanged;

  const IncidentStatusCard({
    super.key,
    required this.incidentStatus,
    required this.onStatusChanged,
  });

  @override
  Widget build(BuildContext context) {
    const statuses = ['Active', 'Investigating', 'Resolved'];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const DetailSectionLabel(icon: Icons.flag_rounded, title: 'Incident Status'),
        Card(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: statuses.map((s) {
                final isSelected = incidentStatus == s;
                final color = AlertSeverityUtils.statusColor(s);
                return Expanded(
                  child: GestureDetector(
                    onTap: () => onStatusChanged(s),
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 220),
                      margin: const EdgeInsets.symmetric(horizontal: 4),
                      padding: const EdgeInsets.symmetric(vertical: 10),
                      decoration: BoxDecoration(
                        color: isSelected ? color : color.withValues(alpha: 0.06),
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(
                          color: isSelected ? color : color.withValues(alpha: 0.2),
                          width: 1,
                        ),
                      ),
                      child: Column(
                        children: [
                          Container(
                            width: 8,
                            height: 8,
                            decoration: BoxDecoration(
                              color: isSelected ? Colors.white : color,
                              shape: BoxShape.circle,
                            ),
                          ),
                          const SizedBox(height: 6),
                          Text(
                            s,
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w700,
                              color: isSelected ? Colors.white : color,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                );
              }).toList(),
            ),
          ),
        ),
      ],
    );
  }
}
