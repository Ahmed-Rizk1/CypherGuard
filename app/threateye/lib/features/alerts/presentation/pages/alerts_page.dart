import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:threateye/injection_container.dart';
import '../manager/alerts_cubit.dart';
import '../manager/alerts_state.dart';
import '../wedgets/alerts_list.dart';
import '../wedgets/empty_state.dart';
import '../wedgets/error_state.dart';
import '../wedgets/skeleton_loading_list.dart';

class AlertsPage extends StatelessWidget {
  const AlertsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      // ← Use the DI container; no more inline construction.
      create: (_) => sl<AlertsCubit>()..loadAlerts(),
      child: const _AlertsView(),
    );
  }
}

// ─── Inner stateful widget keeps the ScrollController lifecycle clean ──────

class _AlertsView extends StatefulWidget {
  const _AlertsView();

  @override
  State<_AlertsView> createState() => _AlertsViewState();
}

class _AlertsViewState extends State<_AlertsView> {
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

  /// Triggers [AlertsCubit.loadMore] when the user scrolls within 200px of
  /// the bottom. The cubit's [AlertsLoaded.isLoadingMore] flag acts as the
  /// scroll guard — the cubit will no-op if a request is already in-flight.
  void _onScroll() {
    final cubit   = context.read<AlertsCubit>();
    final pos     = _scrollController.position;
    const trigger = 200.0; // pixels from bottom

    if (pos.pixels >= pos.maxScrollExtent - trigger) {
      cubit.loadMore();
    }
  }

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<AlertsCubit, AlertsState>(
      builder: (context, state) {
        if (state is AlertsLoading) {
          return const SkeletonLoadingList();
        }
        if (state is AlertsLoaded) {
          if (state.alerts.isEmpty) return const AlertsEmptyState();
          return _AlertsListWithPagination(
            state:            state,
            scrollController: _scrollController,
          );
        }
        if (state is AlertsError) {
          return const AlertsErrorState();
        }
        return const SizedBox.shrink();
      },
    );
  }
}

// ─── List + footer spinner ─────────────────────────────────────────────────

class _AlertsListWithPagination extends StatelessWidget {
  final AlertsLoaded      state;
  final ScrollController  scrollController;

  const _AlertsListWithPagination({
    required this.state,
    required this.scrollController,
  });

  @override
  Widget build(BuildContext context) {
    return AlertsList(
      alerts:           state.alerts,
      scrollController: scrollController,
      footer: state.isLoadingMore
          ? const Padding(
              padding: EdgeInsets.symmetric(vertical: 16),
              child: Center(
                child: SizedBox(
                  width:  24,
                  height: 24,
                  child:  CircularProgressIndicator(strokeWidth: 2),
                ),
              ),
            )
          : state.hasNext
              ? const SizedBox(height: 16)
              : null,
    );
  }
}

