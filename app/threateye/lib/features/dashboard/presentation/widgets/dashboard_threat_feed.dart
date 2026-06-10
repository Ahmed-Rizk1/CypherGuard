import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:threateye/config/theme/app_colors.dart';
import 'package:threateye/config/router/route_names.dart';
import 'package:threateye/features/alerts/domain/entities/attack_alert_entity.dart';
import 'package:threateye/features/alerts/presentation/manager/alerts_cubit.dart';
import 'package:threateye/features/alerts/presentation/manager/alerts_state.dart';
import 'package:threateye/injection_container.dart';

/// Displays the 4 most recent real alerts from [AlertsCubit].
///
/// **No hardcoded data.** This widget creates its own [BlocProvider<AlertsCubit>]
/// (factory registration → fresh instance) and calls [loadAlerts()] once at
/// construction time. The dashboard's own [DashboardCubit] is unaffected.
///
/// States handled:
///   - [AlertsLoading] → subtle skeleton rows
///   - [AlertsLoaded] with items → top-4 live tiles
///   - [AlertsLoaded] empty → mini empty state
///   - anything else → empty [SizedBox]
class DashboardThreatFeed extends StatelessWidget {
  const DashboardThreatFeed({super.key});

  /// Maximum number of alerts shown in the dashboard preview.
  static const int _previewLimit = 4;

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      // Factory → fresh AlertsCubit; does NOT share state with AlertsPage.
      create: (_) => sl<AlertsCubit>()..loadAlerts(),
      child: BlocBuilder<AlertsCubit, AlertsState>(
        builder: (context, state) {
          if (state is AlertsLoading) return _SkeletonFeed();

          if (state is AlertsLoaded) {
            if (state.alerts.isEmpty) return _EmptyFeed();
            final preview = state.alerts.take(_previewLimit).toList();
            return _FeedList(alerts: preview);
          }

          // Error / initial — render nothing (dashboard still shows stats).
          return const SizedBox.shrink();
        },
      ),
    );
  }
}

// ── Skeleton (loading) ─────────────────────────────────────────────────────────

class _SkeletonFeed extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.backgroundCard,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.borderDefault),
      ),
      child: Column(
        children: List.generate(3, (i) {
          final isLast = i == 2;
          return Column(
            children: [
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                child: Row(
                  children: [
                    _Shimmer(width: 34, height: 34, radius: 8),
                    SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          _Shimmer(width: 120, height: 11),
                          SizedBox(height: 5),
                          _Shimmer(width: 80, height: 10),
                        ],
                      ),
                    ),
                    _Shimmer(width: 60, height: 22, radius: 6),
                  ],
                ),
              ),
              if (!isLast)
                const Divider(
                  height: 1,
                  color: AppColors.divider,
                  indent: 16,
                  endIndent: 16,
                ),
            ],
          );
        }),
      ),
    );
  }
}

class _Shimmer extends StatelessWidget {
  final double width;
  final double height;
  final double radius;

  const _Shimmer({required this.width, required this.height, this.radius = 4});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: width,
      height: height,
      decoration: BoxDecoration(
        color: AppColors.borderDefault,
        borderRadius: BorderRadius.circular(radius),
      ),
    );
  }
}

// ── Empty state ────────────────────────────────────────────────────────────────
class _EmptyFeed extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 28, horizontal: 16),
      decoration: BoxDecoration(
        color: AppColors.backgroundCard,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.borderDefault),
      ),
      child: const Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.shield_rounded, size: 32, color: AppColors.textSecondary),
          SizedBox(height: 10),
          Text(
            'No active threats',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: AppColors.textPrimary,
            ),
          ),
          SizedBox(height: 4),
          Text(
            'All systems are operating normally.',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 11, color: AppColors.textSecondary),
          ),
        ],
      ),
    );
  }
}
// ── Live feed list ─────────────────────────────────────────────────────────────

class _FeedList extends StatelessWidget {
  final List<AttackAlertEntity> alerts;

  const _FeedList({required this.alerts});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.backgroundCard,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.borderDefault),
      ),
      child: Column(
        children: [
          ...List.generate(alerts.length, (i) {
            final isLast = i == alerts.length - 1;
            return Column(
              children: [
                _ThreatTile(alert: alerts[i]),
                if (!isLast)
                  const Divider(
                    height: 1,
                    color: AppColors.divider,
                    indent: 16,
                    endIndent: 16,
                  ),
              ],
            );
          }),

          // "View all" footer
          InkWell(
            onTap: () => Navigator.pushNamed(context, RouteNames.alerts),
            borderRadius: const BorderRadius.vertical(
              bottom: Radius.circular(14),
            ),
            child: const Padding(
              padding: EdgeInsets.symmetric(vertical: 10),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    'View all alerts',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: AppColors.primary,
                    ),
                  ),
                  SizedBox(width: 4),
                  Icon(
                    Icons.arrow_forward_rounded,
                    size: 14,
                    color: AppColors.primary,
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ── Individual tile ────────────────────────────────────────────────────────────

class _ThreatTile extends StatelessWidget {
  final AttackAlertEntity alert;

  const _ThreatTile({required this.alert});

  Color get _color {
    switch (alert.severity.toLowerCase()) {
      case 'critical':
        return AppColors.severityCritical;
      case 'high':
        return AppColors.severityHigh;
      case 'medium':
        return AppColors.severityMedium;
      default:
        return AppColors.severityLow;
    }
  }

  IconData get _icon {
    switch (alert.severity.toLowerCase()) {
      case 'critical':
        return Icons.dangerous_rounded;
      case 'high':
        return Icons.warning_rounded;
      case 'medium':
        return Icons.info_rounded;
      default:
        return Icons.check_circle_rounded;
    }
  }

  /// Maps the raw `status` string from the API to a display label.
  String get _statusLabel {
    switch (alert.status.toLowerCase()) {
      case 'new':
        return 'New';
      case 'active':
        return 'Active';
      case 'investigating':
        return 'Investigating';
      case 'resolved':
        return 'Resolved';
      default:
        return alert.status;
    }
  }

  /// Attempts to show a relative time label.
  /// Falls back gracefully if the time string cannot be parsed.
  String get _timeLabel {
    try {
      final t = DateTime.parse(alert.time).toLocal();
      final diff = DateTime.now().difference(t);
      if (diff.inSeconds < 60) return 'Just now';
      if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
      if (diff.inHours < 24) return '${diff.inHours}h ago';
      return '${diff.inDays}d ago';
    } catch (_) {
      return alert.time; // raw string fallback
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      child: Row(
        children: [
          // Severity icon
          Container(
            width: 34,
            height: 34,
            decoration: BoxDecoration(
              color: _color.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(_icon, color: _color, size: 18),
          ),
          const SizedBox(width: 12),

          // Attack type + IP · time
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  alert.attackType,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textPrimary,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  '${alert.sourceIp}  ·  $_timeLabel',
                  style: const TextStyle(
                    fontSize: 11,
                    color: AppColors.textSecondary,
                  ),
                ),
              ],
            ),
          ),

          // Status badge
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(
              color: _color.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Text(
              _statusLabel,
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w700,
                color: _color,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
