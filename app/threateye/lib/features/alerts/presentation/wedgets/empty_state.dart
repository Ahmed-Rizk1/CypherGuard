import 'package:flutter/material.dart';

class AlertsEmptyState extends StatelessWidget {
  const AlertsEmptyState({super.key});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            padding: const EdgeInsets.all(22),
            decoration: BoxDecoration(
              color: Colors.green.withValues(alpha: 0.1),
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.verified_user_outlined,
              size: 52,
              color: Colors.green,
            ),
          ),
          const SizedBox(height: 20),
          const Text(
            'All Clear',
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w700,
              decoration: TextDecoration.none,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            'No active alerts detected.',
            style: TextStyle(
              fontSize: 14,
              decoration: TextDecoration.none,
              color: Theme.of(
                context,
              ).colorScheme.onSurface.withValues(alpha: 0.5),
            ),
          ),
        ],
      ),
    );
  }
}
