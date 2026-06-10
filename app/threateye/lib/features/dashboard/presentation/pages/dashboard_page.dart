import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:threateye/config/theme/app_colors.dart';
import 'package:threateye/injection_container.dart';
import 'package:threateye/features/dashboard/domain/entities/dashboard_summary_entity.dart';
import '../manager/dashboard_cubit.dart';
import '../manager/dashboard_state.dart';
import '../widgets/dashboard_header.dart';
import '../widgets/dashboard_quick_response.dart';
import '../widgets/dashboard_section_label.dart';
import '../widgets/dashboard_security_status.dart';
import '../widgets/dashboard_stats_grid.dart';
import '../widgets/dashboard_threat_feed.dart';

class DashboardPage extends StatelessWidget {
  const DashboardPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => sl<DashboardCubit>()..loadDashboard(),
      child: BlocBuilder<DashboardCubit, DashboardState>(
        builder: (context, state) {
          if (state is DashboardLoading) return const _LoadingView();
          if (state is DashboardError) return const _ErrorView();
          if (state is DashboardLoaded)
            return _DashboardBody(summary: state.summary);
          return const SizedBox.shrink();
        },
      ),
    );
  }
}

class _LoadingView extends StatelessWidget {
  const _LoadingView();

  @override
  Widget build(BuildContext context) => const Center(
    child: Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        CircularProgressIndicator(color: AppColors.primaryLight),
        SizedBox(height: 16),
        Text(
          'Loading SOC Dashboard…',
          style: TextStyle(color: AppColors.textSecondary, fontSize: 13),
        ),
      ],
    ),
  );
}

class _ErrorView extends StatelessWidget {
  const _ErrorView();

  @override
  Widget build(BuildContext context) => const Center(
    child: Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(
          Icons.cloud_off_rounded,
          size: 48,
          color: AppColors.severityCritical,
        ),
        SizedBox(height: 12),
        Text(
          'Failed to load dashboard.',
          style: TextStyle(color: AppColors.textSecondary),
        ),
      ],
    ),
  );
}

// ─── Body ─────────────────────────────────────────────────────────────────────

class _DashboardBody extends StatelessWidget {
  final DashboardSummaryEntity summary;
  const _DashboardBody({required this.summary});

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      color: AppColors.primaryLight,
      backgroundColor: AppColors.backgroundCard,
      onRefresh: () async => context.read<DashboardCubit>().loadDashboard(),
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 1. Header
            DashboardHeader(summary: summary),
            const SizedBox(height: 20),

            // 2. Stats grid
            const DashboardSectionLabel(
              label: 'Security Overview',
              icon: Icons.bar_chart_rounded,
            ),
            const SizedBox(height: 10),
            DashboardStatsGrid(summary: summary),
            const SizedBox(height: 24),

            // 3. Live threat feed
            const DashboardSectionLabel(
              label: 'Live Threat Activity',
              icon: Icons.sensors_rounded,
              trailingLabel: 'LIVE',
              trailingColor: AppColors.severityCritical,
            ),
            const SizedBox(height: 10),
            const DashboardThreatFeed(),
            const SizedBox(height: 24),

            // 4. Quick response
            const DashboardSectionLabel(
              label: 'Quick Response',
              icon: Icons.bolt_rounded,
            ),
            const SizedBox(height: 10),
            const DashboardQuickResponse(),
            const SizedBox(height: 24),

            // 5. Security status
            const DashboardSectionLabel(
              label: 'Security Status',
              icon: Icons.verified_user_rounded,
            ),
            const SizedBox(height: 10),
            const DashboardSecurityStatus(),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }
}
