import 'package:threateye/features/decision/domain/entities/decision_entity.dart';

// ─── Base ───────────────────────────────────────────────────────────────────

abstract class DecisionState {}

// ─── History list states ─────────────────────────────────────────────────────

class DecisionInitial extends DecisionState {}

/// First-page load in progress (show skeleton).
class DecisionLoading extends DecisionState {}

/// At least one page of decision history loaded.
class DecisionLoaded extends DecisionState {
  final List<DecisionEntity> decisions;
  final String?              cursor;
  final bool                 hasNext;

  /// True while a `loadMore()` call is in-flight — acts as scroll guard.
  final bool                 isLoadingMore;

  DecisionLoaded({
    required this.decisions,
    required this.cursor,
    required this.hasNext,
    this.isLoadingMore = false,
  });

  DecisionLoaded copyWith({
    List<DecisionEntity>? decisions,
    String?               cursor,
    bool?                 hasNext,
    bool?                 isLoadingMore,
  }) =>
      DecisionLoaded(
        decisions:     decisions     ?? this.decisions,
        cursor:        cursor        ?? this.cursor,
        hasNext:       hasNext       ?? this.hasNext,
        isLoadingMore: isLoadingMore ?? this.isLoadingMore,
      );
}

/// Non-recoverable error loading history.
class DecisionError extends DecisionState {
  final String message;
  DecisionError(this.message);
}

// ─── Submit action states ─────────────────────────────────────────────────────

/// A POST /decision request is in-flight — disable all action buttons.
class DecisionActionInProgress extends DecisionState {}

/// Decision submitted successfully.
class DecisionActionSuccess extends DecisionState {
  final DecisionEntity decision;
  DecisionActionSuccess(this.decision);
}

/// Decision submission failed.
class DecisionActionError extends DecisionState {
  final String message;
  DecisionActionError(this.message);
}

/// Decision could not be submitted (device offline) and has been saved to the
/// local queue. The [OfflineQueueService] will deliver it automatically when
/// network connectivity is restored.
class DecisionActionQueued extends DecisionState {
  DecisionActionQueued();
}
