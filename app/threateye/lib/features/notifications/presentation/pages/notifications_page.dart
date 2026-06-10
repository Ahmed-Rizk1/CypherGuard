import 'dart:async';

import 'package:flutter/material.dart';
import 'package:threateye/config/router/route_names.dart';
import 'package:threateye/core/services/websocket_manager_service.dart';
import 'package:threateye/injection_container.dart';

// ── In-memory notification model ──────────────────────────────────────────────

/// Lightweight model for a notification entry derived from a WebSocket event.
class _LiveNotification {
  final String id;
  final String title;
  final String message;
  final String type;
  final DateTime receivedAt;

  const _LiveNotification({
    required this.id,
    required this.title,
    required this.message,
    required this.type,
    required this.receivedAt,
  });

  String get timeLabel {
    final now  = DateTime.now();
    final diff = now.difference(receivedAt);
    if (diff.inSeconds < 60)  return 'Just now';
    if (diff.inMinutes < 60)  return '${diff.inMinutes}m ago';
    if (diff.inHours   < 24)  return '${diff.inHours}h ago';
    return '${diff.inDays}d ago';
  }
}

// ── Page ──────────────────────────────────────────────────────────────────────

/// Displays real-time security events received via [WebSocketManagerService].
///
/// No mock data. No hardcoded cards.
///
/// Every `new_alert` frame pushed by the backend is prepended to an in-memory
/// list. The list is rebuilt on the next frame via [setState]. If the
/// WebSocket is not yet connected or no events have arrived, a clean empty
/// state is shown.
///
/// **Lifetime:** the page is StatefulWidget so the stream subscription is
/// properly cancelled in [dispose] — no leaks.
class NotificationsPage extends StatefulWidget {
  const NotificationsPage({super.key});

  @override
  State<NotificationsPage> createState() => _NotificationsPageState();
}

class _NotificationsPageState extends State<NotificationsPage> {
  late final WebSocketManagerService _ws;
  StreamSubscription<Map<String, dynamic>>? _sub;

  final List<_LiveNotification> _notifications = [];

  @override
  void initState() {
    super.initState();
    _ws  = sl<WebSocketManagerService>();
    _sub = _ws.messageStream.listen(_onMessage);
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }

  void _onMessage(Map<String, dynamic> msg) {
    final type = msg['type'] as String?;
    if (type != 'new_alert') return;

    final data       = msg['data'] as Map<String, dynamic>? ?? msg;
    final attackType = (data['attack_type'] ?? data['attackType'] ?? 'Security Event').toString();
    final severity   = (data['severity']   ?? 'medium').toString().toUpperCase();
    final sourceIp   = (data['src_ip']     ?? data['source_ip'] ?? 'Unknown').toString();
    final id         = (data['id']         ?? DateTime.now().millisecondsSinceEpoch.toString()).toString();

    final notification = _LiveNotification(
      id:         id,
      title:      '$attackType Detected',
      message:    'Severity: $severity • Source: $sourceIp',
      type:       'Alert',
      receivedAt: DateTime.now(),
    );

    if (!mounted) return;
    setState(() => _notifications.insert(0, notification));
  }

  @override
  Widget build(BuildContext context) {
    final theme    = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Scaffold(
      backgroundColor: colorScheme.surface,
      body: _notifications.isEmpty
          ? _buildEmptyState(theme)
          : _buildList(theme, colorScheme),
    );
  }

  // ── Empty state ─────────────────────────────────────────────────────────────

  Widget _buildEmptyState(ThemeData theme) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: theme.colorScheme.surfaceContainerHighest
                  .withValues(alpha: 0.6),
              shape: BoxShape.circle,
            ),
            child: Icon(
              Icons.notifications_none_rounded,
              size: 52,
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 20),
          Text(
            'No Notifications',
            style: theme.textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            'Live security events will appear here\nwhen the backend pushes them.',
            textAlign: TextAlign.center,
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ],
      ),
    );
  }

  // ── Notification list ────────────────────────────────────────────────────────

  Widget _buildList(ThemeData theme, ColorScheme cs) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // ── Header ──────────────────────────────────────────────────────────
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 48, 16, 8),
          child: Row(
            children: [
              Expanded(
                child: Text(
                  'Live Events',
                  style: theme.textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              // Badge showing count
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: cs.errorContainer,
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(
                  '${_notifications.length}',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    color: cs.onErrorContainer,
                  ),
                ),
              ),
            ],
          ),
        ),

        // ── List ─────────────────────────────────────────────────────────────
        Expanded(
          child: ListView.separated(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            itemCount: _notifications.length,
            separatorBuilder: (_, __) => const SizedBox(height: 6),
            itemBuilder: (context, index) =>
                _NotificationCard(notification: _notifications[index]),
          ),
        ),
      ],
    );
  }
}

// ── Card widget ────────────────────────────────────────────────────────────────

class _NotificationCard extends StatelessWidget {
  final _LiveNotification notification;

  const _NotificationCard({required this.notification});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs    = theme.colorScheme;

    // Alert type → colour mapping
    const alertColor = Color(0xFFEF4444); // red-500
    const alertBg    = Color(0x1AEF4444); // red-500 @ 10%

    return Material(
      color: theme.colorScheme.surfaceContainerLow,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () =>
            Navigator.pushNamed(context, RouteNames.alerts),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Icon
              Container(
                padding: const EdgeInsets.all(10),
                decoration: const BoxDecoration(
                  color: alertBg,
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.warning_amber_rounded,
                  color: alertColor,
                  size: 18,
                ),
              ),
              const SizedBox(width: 12),

              // Content
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      notification.title,
                      style: theme.textTheme.bodyMedium?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      notification.message,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: cs.onSurfaceVariant,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 10),

              // Time + badge
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    notification.timeLabel,
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: cs.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8, vertical: 3,
                    ),
                    decoration: BoxDecoration(
                      color: alertBg,
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: const Text(
                      'LIVE',
                      style: TextStyle(
                        fontSize: 9,
                        fontWeight: FontWeight.w800,
                        color: alertColor,
                        letterSpacing: 0.5,
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
