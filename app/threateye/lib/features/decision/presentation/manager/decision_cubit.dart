import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:threateye/core/error/failures.dart';
import 'package:threateye/core/services/offline_queue_service.dart';
import '../../domain/usecases/get_decision_history_usecase.dart';
import '../../domain/usecases/submit_decision_usecase.dart';
import 'decision_state.dart';

/// Presentation-layer state machine for the Decision Flow.
///
/// **Phase 6 — Offline Resilience:**
/// When [submitDecision] receives a [NetworkFailure], rather than emitting
/// [DecisionActionError] with a dead-end message, the payload is handed to
/// [OfflineQueueService.enqueue]. The cubit then emits
/// [DecisionActionQueued] so the UI can show a "saved for later" banner
/// instead of a failure banner. The item will be automatically pushed to
/// the server by [OfflineQueueService] when connectivity is restored.
class DecisionCubit extends Cubit<DecisionState> {
  final GetDecisionHistoryUseCase getDecisionHistoryUseCase;
  final SubmitDecisionUseCase submitDecisionUseCase;

  /// Phase 6: injected offline queue. Nullable for backward compatibility
  /// with any test that creates [DecisionCubit] without the queue.
  final OfflineQueueService? offlineQueue;

  DecisionCubit({
    required this.getDecisionHistoryUseCase,
    required this.submitDecisionUseCase,
    this.offlineQueue,
  }) : super(DecisionInitial());

  // ── loadHistory ─────────────────────────────────────────────────────────────

  /// Performs a fresh first-page load of decision history.
  Future<void> loadHistory() async {
    emit(DecisionLoading());

    final result = await getDecisionHistoryUseCase();

    result.fold(
      (failure) => emit(DecisionError(failure.message)),
      (page) => emit(
        DecisionLoaded(
          decisions: page.items,
          cursor: page.cursor,
          hasNext: page.hasNext,
        ),
      ),
    );
  }

  // ── loadMore ────────────────────────────────────────────────────────────────

  /// Appends the next page to the history list.
  ///
  /// Guards against duplicate in-flight requests via [DecisionLoaded.isLoadingMore].
  Future<void> loadMore() async {
    final current = state;
    if (current is! DecisionLoaded) return;
    if (!current.hasNext) return;
    if (current.isLoadingMore) return; // scroll guard

    emit(current.copyWith(isLoadingMore: true));

    final result = await getDecisionHistoryUseCase(cursor: current.cursor);

    result.fold(
      (_) => emit(current.copyWith(isLoadingMore: false)),
      (page) => emit(
        current.copyWith(
          decisions: [...current.decisions, ...page.items],
          cursor: page.cursor,
          hasNext: page.hasNext,
          isLoadingMore: false,
        ),
      ),
    );
  }

  // ── submitDecision ──────────────────────────────────────────────────────────

  /// Sends a POST /decision for the given alert.
  ///
  /// Emits [DecisionActionInProgress] immediately to disable action buttons.
  ///
  /// **Happy path:** emits [DecisionActionSuccess] then silently refreshes
  /// the history list.
  ///
  /// **Network failure (offline):** enqueues the decision locally and emits
  /// [DecisionActionQueued] — the UI should show a "saved, will retry" banner.
  ///
  /// **Other failure:** emits [DecisionActionError] as before.
  Future<void> submitDecision({
    required String alertId,
    required String action,
    String? note,
  }) async {
    emit(DecisionActionInProgress());

    final result = await submitDecisionUseCase(
      alertId: alertId,
      action: action,
      note: note,
    );

    result.fold(
      (failure) {
        // ── Phase 6: offline resilience ────────────────────────────────────
        if (failure is NetworkFailure && offlineQueue != null) {
          offlineQueue!.enqueue(
            PendingDecision(
              alertId: alertId,
              action: action,
              note: note,
              queuedAt: DateTime.now().toUtc(),
            ),
          );
          emit(DecisionActionQueued());
          return;
        }
        // ── All other failures ─────────────────────────────────────────────
        emit(DecisionActionError(failure.message));
      },
      (decision) {
        emit(DecisionActionSuccess(decision));
        // Silently refresh the list so the new decision appears at the top.
        _refreshHistorySilently();
      },
    );
  }

  // ── private helper ──────────────────────────────────────────────────────────

  Future<void> _refreshHistorySilently() async {
    final result = await getDecisionHistoryUseCase();
    result.fold(
      (_) => null, // ignore silent refresh failures
      (page) {
        // Only update if not in a transient action state.
        if (state is DecisionActionSuccess || state is DecisionActionError)
          return;
        emit(
          DecisionLoaded(
            decisions: page.items,
            cursor: page.cursor,
            hasNext: page.hasNext,
          ),
        );
      },
    );
  }
}
