import 'package:flutter/material.dart';

class SeverityBar extends StatelessWidget {
  final int total, critical, high, medium, low;
  const SeverityBar({
    super.key,
    required this.total,
    required this.critical,
    required this.high,
    required this.medium,
    required this.low,
  });

  @override
  Widget build(BuildContext context) {
    if (total == 0) return const SizedBox.shrink();

    return ClipRRect(
      borderRadius: BorderRadius.circular(6),
      child: Row(
        children: [
          _bar(critical, const Color(0xFFEF4444)),
          _bar(high, const Color(0xFFF97316)),
          _bar(medium, const Color(0xFFF59E0B)),
          _bar(low, const Color(0xFF22C55E)),
        ],
      ),
    );
  }

  Widget _bar(int count, Color color) {
    if (count == 0) return const SizedBox.shrink();
    return Expanded(
      flex: count,
      child: Container(height: 6, color: color),
    );
  }
}
