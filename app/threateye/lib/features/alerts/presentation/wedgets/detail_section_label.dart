import 'package:flutter/material.dart';

class DetailSectionLabel extends StatelessWidget {
  final IconData icon;
  final String title;

  const DetailSectionLabel({
    super.key,
    required this.icon,
    required this.title,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        children: [
          Icon(icon, size: 15, color: Colors.blueAccent),
          const SizedBox(width: 6),
          Text(
            title.toUpperCase(),
            style: const TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w800,
              color: Colors.blueAccent,
              letterSpacing: 1.1,
            ),
          ),
        ],
      ),
    );
  }
}
