import 'package:threateye/features/alerts/domain/entities/attack_alert_entity.dart';

// ─── Base ──────────────────────────────────────────────────────────────────

abstract class AlertsState {}

// ─── List states ───────────────────────────────────────────────────────────

class AlertsInitial extends AlertsState {}

/// First-page fetch in progress (show skeleton).
class AlertsLoading extends AlertsState {}

/// At least one page loaded successfully.
class AlertsLoaded extends AlertsState {
  final List<AttackAlertEntity> alerts;

  /// Opaque cursor for the next page. `null` when [hasNext] is false.
  final String? cursor;

  /// Whether there is a next page available.
  final bool hasNext;

  final bool isLoadingMore;

  AlertsLoaded({
    required this.alerts,
    required this.cursor,
    required this.hasNext,
    this.isLoadingMore = false,
  });

  AlertsLoaded copyWith({
    List<AttackAlertEntity>? alerts,
    String? cursor,
    bool? hasNext,
    bool? isLoadingMore,
  }) {
    return AlertsLoaded(
      alerts: alerts ?? this.alerts,
      cursor: cursor ?? this.cursor,
      hasNext: hasNext ?? this.hasNext,
      isLoadingMore: isLoadingMore ?? this.isLoadingMore,
    );
  }
}

/// Non-recoverable list error.
class AlertsError extends AlertsState {
  final String message;
  AlertsError(this.message);
}

// ─── Detail states ─────────────────────────────────────────────────────────

/// Loading a single alert detail.
class AlertDetailLoading extends AlertsState {}

/// Single alert loaded successfully.
class AlertDetailLoaded extends AlertsState {
  final AttackAlertEntity alert;
  AlertDetailLoaded(this.alert);
}

/// The requested alert does not exist on the server (404 → [NotFoundFailure]).
///
/// The UI should show "This alert no longer exists" instead of a generic error.
class AlertDetailNotFound extends AlertsState {
  final String message;
  AlertDetailNotFound(this.message);
}

/// Error loading a single alert.
class AlertDetailError extends AlertsState {
  final String message;
  AlertDetailError(this.message);
}

// ─── Action states (PATCH) ─────────────────────────────────────────────────

/// A PATCH status-update request is in-flight.
///
/// The UI must disable action buttons while this state is active
/// to prevent duplicate submissions (Tech Lead constraint).
class AlertActionInProgress extends AlertsState {
  final AttackAlertEntity alert;
  AlertActionInProgress(this.alert);
}

/// PATCH succeeded — the alert was updated to [updatedAlert].
class AlertActionSuccess extends AlertsState {
  final AttackAlertEntity updatedAlert;
  AlertActionSuccess(this.updatedAlert);
}

/// PATCH failed.
class AlertActionError extends AlertsState {
  final AttackAlertEntity alert; // the original alert, so UI can revert
  final String message;
  AlertActionError({required this.alert, required this.message});
}
