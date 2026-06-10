import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:threateye/injection_container.dart';
import '../../domain/entities/decision_entity.dart';
import '../manager/decision_cubit.dart';
import '../manager/decision_state.dart';

class DecisionHistoryPage extends StatelessWidget {
  const DecisionHistoryPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => sl<DecisionCubit>()..loadHistory(),
      child: const _DecisionHistoryView(),
    );
  }
}

// ── Inner stateful view ──────────────────────────────────────────────────────

class _DecisionHistoryView extends StatefulWidget {
  const _DecisionHistoryView();

  @override
  State<_DecisionHistoryView> createState() => _DecisionHistoryViewState();
}

class _DecisionHistoryViewState extends State<_DecisionHistoryView> {
  late final ScrollController _scrollController;

  @override
  void initState() {
    super.initState();
    _scrollController = ScrollController()..addListener(_onScroll);
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    final pos     = _scrollController.position;
    const trigger = 200.0;
    if (pos.pixels >= pos.maxScrollExtent - trigger) {
      context.read<DecisionCubit>().loadMore();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0E1A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF111827),
        surfaceTintColor: Colors.transparent,
        title: const Text(
          'Decision History',
          style: TextStyle(
            fontWeight: FontWeight.w700,
            color: Colors.white,
            fontSize: 18,
          ),
        ),
        iconTheme: const IconThemeData(color: Colors.white),
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(1),
          child: Container(
            height: 1,
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                colors: [Color(0xFF6366F1), Color(0x006366F1)],
              ),
            ),
          ),
        ),
      ),
      body: BlocBuilder<DecisionCubit, DecisionState>(
        builder: (context, state) {
          if (state is DecisionLoading) {
            return const _DecisionSkeleton();
          }
          if (state is DecisionLoaded) {
            if (state.decisions.isEmpty) {
              return const _DecisionEmpty();
            }
            return _DecisionList(
              state:            state,
              scrollController: _scrollController,
            );
          }
          if (state is DecisionError) {
            return _DecisionErrorState(
              message:   state.message,
              onRetry:   () => context.read<DecisionCubit>().loadHistory(),
            );
          }
          return const SizedBox.shrink();
        },
      ),
    );
  }
}

// ── List ─────────────────────────────────────────────────────────────────────

class _DecisionList extends StatelessWidget {
  final DecisionLoaded     state;
  final ScrollController   scrollController;

  const _DecisionList({
    required this.state,
    required this.scrollController,
  });

  @override
  Widget build(BuildContext context) {
    return ListView.separated(
      controller: scrollController,
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
      itemCount: state.decisions.length + (state.isLoadingMore ? 1 : 0),
      separatorBuilder: (_, __) => const SizedBox(height: 10),
      itemBuilder: (context, index) {
        if (index == state.decisions.length) {
          // Footer spinner during pagination
          return const Padding(
            padding: EdgeInsets.symmetric(vertical: 16),
            child: Center(
              child: SizedBox(
                width:  24,
                height: 24,
                child:  CircularProgressIndicator(strokeWidth: 2),
              ),
            ),
          );
        }
        return _DecisionCard(decision: state.decisions[index]);
      },
    );
  }
}

// ── Decision Card ─────────────────────────────────────────────────────────────

class _DecisionCard extends StatelessWidget {
  final DecisionEntity decision;

  const _DecisionCard({required this.decision});

  Color get _actionColor {
    switch (decision.action) {
      case DecisionAction.approve:
        return const Color(0xFF22C55E);
      case DecisionAction.reject:
        return const Color(0xFFEF4444);
      case DecisionAction.escalate:
        return const Color(0xFFF97316);
    }
  }

  IconData get _actionIcon {
    switch (decision.action) {
      case DecisionAction.approve:
        return Icons.check_circle_rounded;
      case DecisionAction.reject:
        return Icons.cancel_rounded;
      case DecisionAction.escalate:
        return Icons.arrow_circle_up_rounded;
    }
  }

  String get _actionLabel {
    switch (decision.action) {
      case DecisionAction.approve:
        return 'APPROVED';
      case DecisionAction.reject:
        return 'REJECTED';
      case DecisionAction.escalate:
        return 'ESCALATED';
    }
  }

  @override
  Widget build(BuildContext context) {
    final color = _actionColor;

    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFF111827),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withValues(alpha: 0.25)),
        boxShadow: [
          BoxShadow(
            color:  color.withValues(alpha: 0.06),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Header row ─────────────────────────────────────────────────
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color:        color.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(_actionIcon, color: color, size: 20),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _actionLabel,
                        style: TextStyle(
                          color:      color,
                          fontWeight: FontWeight.w800,
                          fontSize:   13,
                          letterSpacing: 1.1,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        'Alert: ${decision.alertId}',
                        style: const TextStyle(
                          color:    Color(0xFF9CA3AF),
                          fontSize: 12,
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                ),
                // Timestamp chip
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color:        const Color(0xFF1F2937),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    _formatDate(decision.decidedAt),
                    style: const TextStyle(
                      color:    Color(0xFF6B7280),
                      fontSize: 11,
                    ),
                  ),
                ),
              ],
            ),

            // ── Analyst & note ─────────────────────────────────────────────
            if (decision.analystId != null || decision.note != null) ...[
              const SizedBox(height: 12),
              const Divider(color: Color(0xFF1F2937), height: 1),
              const SizedBox(height: 10),
              if (decision.analystId != null)
                Row(
                  children: [
                    const Icon(
                      Icons.person_outline_rounded,
                      color: Color(0xFF6B7280),
                      size: 14,
                    ),
                    const SizedBox(width: 6),
                    Text(
                      decision.analystId!,
                      style: const TextStyle(
                        color:    Color(0xFF9CA3AF),
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              if (decision.note != null) ...[
                const SizedBox(height: 6),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(
                      Icons.notes_rounded,
                      color: Color(0xFF6B7280),
                      size: 14,
                    ),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        decision.note!,
                        style: const TextStyle(
                          color:    Color(0xFF9CA3AF),
                          fontSize: 12,
                          fontStyle: FontStyle.italic,
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ],
          ],
        ),
      ),
    );
  }

  String _formatDate(String iso) {
    try {
      final dt = DateTime.parse(iso).toLocal();
      return '${dt.day.toString().padLeft(2, '0')}/${dt.month.toString().padLeft(2, '0')} '
             '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
    } catch (_) {
      return iso;
    }
  }
}

// ── Skeleton ─────────────────────────────────────────────────────────────────

class _DecisionSkeleton extends StatelessWidget {
  const _DecisionSkeleton();

  @override
  Widget build(BuildContext context) {
    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
      itemCount: 6,
      separatorBuilder: (_, __) => const SizedBox(height: 10),
      itemBuilder: (_, __) => Container(
        height: 90,
        decoration: BoxDecoration(
          color:        const Color(0xFF111827),
          borderRadius: BorderRadius.circular(16),
        ),
      ),
    );
  }
}

// ── Empty state ───────────────────────────────────────────────────────────────

class _DecisionEmpty extends StatelessWidget {
  const _DecisionEmpty();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.history_toggle_off_rounded, size: 64, color: Color(0xFF374151)),
          SizedBox(height: 16),
          Text(
            'No decisions recorded yet.',
            style: TextStyle(color: Color(0xFF6B7280), fontSize: 16),
          ),
        ],
      ),
    );
  }
}

// ── Error state ───────────────────────────────────────────────────────────────

class _DecisionErrorState extends StatelessWidget {
  final String    message;
  final VoidCallback onRetry;

  const _DecisionErrorState({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline_rounded, size: 56, color: Color(0xFFEF4444)),
            const SizedBox(height: 16),
            Text(
              message,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Color(0xFF9CA3AF), fontSize: 15),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: onRetry,
              icon:  const Icon(Icons.refresh_rounded),
              label: const Text('Retry'),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF6366F1),
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
