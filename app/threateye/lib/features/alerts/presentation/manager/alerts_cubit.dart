import 'dart:async';

import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:threateye/core/error/failures.dart';
import 'package:threateye/core/services/local_notification_service.dart';
import 'package:threateye/core/services/logger_service.dart';
import 'package:threateye/core/services/websocket_manager_service.dart';
import '../../domain/entities/attack_alert_entity.dart';
import '../../domain/usecases/get_alert_by_id_usecase.dart';
import '../../domain/usecases/get_alerts_usecase.dart';
import '../../domain/usecases/update_alert_status_usecase.dart';
import 'alerts_state.dart';

class AlertsCubit extends Cubit<AlertsState> {
  final GetAlertsUseCase getAlertsUseCase;
  final GetAlertByIdUseCase getAlertByIdUseCase;
  final UpdateAlertStatusUseCase updateAlertStatusUseCase;
  final WebSocketManagerService webSocketManagerService;

  /// Holds the active WebSocket subscription so we can cancel it in [close].
  StreamSubscription<Map<String, dynamic>>? _wsSub;

  AlertsCubit({
    required this.getAlertsUseCase,
    required this.getAlertByIdUseCase,
    required this.updateAlertStatusUseCase,
    required this.webSocketManagerService,
  }) : super(AlertsInitial()) {
    _subscribeToWebSocket();
  }

  // ── Active filter state ────────────────────────────────────────────────────

  String? _activeSeverity;
  String? _activeStatus;

  // ── WebSocket real-time integration ────────────────────────────────────────

  /// Subscribes to the live WebSocket stream once at construction time.
  ///
  /// Handles `new_alert` events by prepending the parsed alert to the
  /// existing [AlertsLoaded] list — no REST call, pagination state intact.
  void _subscribeToWebSocket() {
    _wsSub = webSocketManagerService.messageStream.listen(
      _onWebSocketMessage,
      onError: (Object e) {
        LoggerService.warning('[AlertsCubit] WebSocket stream error: $e');
      },
      cancelOnError: false,
    );
  }

  void _onWebSocketMessage(Map<String, dynamic> message) {
    final type = message['type'] as String?;
    if (type != 'new_alert') return;

    // Only update the list when it is currently loaded — ignore during
    // loading, detail, or action states.
    final current = state;
    if (current is! AlertsLoaded) return;

    try {
      final payload = message['data'] as Map<String, dynamic>? ?? message;
      final newAlert = _parseAlertFromWs(payload);

      // Prepend: newest alert appears at the top without disturbing pagination.
      emit(current.copyWith(alerts: [newAlert, ...current.alerts]));

      // Fire a local device notification so the analyst is alerted immediately,
      // even while looking at another screen. No Firebase required.
      LocalNotificationService.showAlertNotification(
        id: newAlert.id.hashCode,
        title: ' ${newAlert.attackType} Detected',
        body:
            'Severity: ${newAlert.severity.toUpperCase()} • Source: ${newAlert.sourceIp}',
      );

      LoggerService.info(
        '[AlertsCubit] Real-time alert prepended: ${newAlert.id}',
      );
    } catch (e) {
      LoggerService.warning(
        '[AlertsCubit] Failed to parse new_alert payload: $e',
      );
    }
  }

  /// Parses a raw WebSocket payload into an [AttackAlertEntity].
  ///
  /// Field names mirror the REST API response so the same model layer works
  /// for both REST and WebSocket events.
  AttackAlertEntity _parseAlertFromWs(Map<String, dynamic> d) {
    return AttackAlertEntity(
      id: (d['id'] ?? '').toString(),
      attackType: (d['attack_type'] ?? d['attackType'] ?? 'Unknown').toString(),
      severity: (d['severity'] ?? 'medium').toString(),
      status: (d['status'] ?? 'new').toString(),
      time: (d['time'] ?? d['created_at'] ?? '').toString(),
      sourceIp: (d['src_ip'] ?? d['sourceIp'] ?? '').toString(),
      description: d['description'] as String?,
      targetIp: (d['dst_ip'] ?? d['targetIp']) as String?,
    );
  }

  // ── loadAlerts ─────────────────────────────────────────────────────────────

  /// Performs a fresh first-page load.
  ///
  /// Resets all pagination state. Pass [severity] / [status] to apply filters.
  Future<void> loadAlerts({String? severity, String? status}) async {
    _activeSeverity = severity;
    _activeStatus = status;

    emit(AlertsLoading());

    final result = await getAlertsUseCase(severity: severity, status: status);

    result.fold(
      (failure) => emit(AlertsError(failure.message)),
      (page) => emit(
        AlertsLoaded(
          alerts: page.items,
          cursor: page.cursor,
          hasNext: page.hasNext,
        ),
      ),
    );
  }

  // ── loadMore ───────────────────────────────────────────────────────────────

  /// Appends the next page to the current list.
  ///
  /// **Scroll guard**: returns early if a load-more is already in-flight
  /// ([AlertsLoaded.isLoadingMore] == true) or there are no more pages,
  /// preventing duplicate network requests on rapid scroll events.
  Future<void> loadMore() async {
    final current = state;
    if (current is! AlertsLoaded) return;
    if (!current.hasNext) return; // no more pages
    if (current.isLoadingMore) return; // ← scroll guard: debounce

    // Mark loading-more so the UI can show a footer spinner.
    emit(current.copyWith(isLoadingMore: true));

    final result = await getAlertsUseCase(
      severity: _activeSeverity,
      status: _activeStatus,
      cursor: current.cursor,
    );

    result.fold(
      (failure) {
        // Revert to the stable loaded state with loading flag cleared.
        emit(current.copyWith(isLoadingMore: false));
      },
      (page) {
        emit(
          current.copyWith(
            alerts: [...current.alerts, ...page.items],
            cursor: page.cursor,
            hasNext: page.hasNext,
            isLoadingMore: false,
          ),
        );
      },
    );
  }

  // ── getAlertById ───────────────────────────────────────────────────────────

  /// Fetches a single alert for the detail page.
  ///
  /// Graceful [NotFoundFailure] handling: emits [AlertDetailNotFound] with a
  /// descriptive message instead of a generic error, satisfying the Tech Lead
  /// constraint for "this alert no longer exists" UX.
  Future<void> getAlertById(String id) async {
    emit(AlertDetailLoading());

    final result = await getAlertByIdUseCase(id);

    result.fold((failure) {
      if (failure is NotFoundFailure) {
        emit(AlertDetailNotFound(failure.message));
      } else {
        emit(AlertDetailError(failure.message));
      }
    }, (alert) => emit(AlertDetailLoaded(alert)));
  }

  // ── updateStatus ───────────────────────────────────────────────────────────

  /// Sends a PATCH to update the alert status.
  ///
  /// **UI State Protection**: emits [AlertActionInProgress] immediately so
  /// the UI can disable action buttons before the network call completes,
  /// preventing duplicate PATCH submissions (Tech Lead constraint).
  ///
  /// On success: emits [AlertActionSuccess] then refreshes the list.
  /// On failure: emits [AlertActionError] carrying the original [alert] so
  ///             the UI can revert any optimistic UI changes.
  Future<void> updateStatus({
    required String id,
    required String newStatus,
    required dynamic alert, // AttackAlertEntity — avoids circular import issues
  }) async {
    emit(AlertActionInProgress(alert));

    final result = await updateAlertStatusUseCase(id: id, status: newStatus);

    result.fold(
      (failure) =>
          emit(AlertActionError(alert: alert, message: failure.message)),
      (updatedAlert) {
        emit(AlertActionSuccess(updatedAlert));
        // Silently refresh the list in the background so it reflects the change.
        _refreshListSilently();
      },
    );
  }

  // ── helpers ────────────────────────────────────────────────────────────────

  /// Re-fetches the first page with the active filters without emitting
  /// [AlertsLoading] so the UI does not flash while still on the detail page.
  Future<void> _refreshListSilently() async {
    final result = await getAlertsUseCase(
      severity: _activeSeverity,
      status: _activeStatus,
    );

    result.fold(
      (_) {}, // ignore refresh failures silently
      (page) {
        // Only update list state if we're not in a detail/action state
        if (state is AlertActionSuccess || state is AlertActionError) {
          // Leave the current state; the user is still on detail page.
          return;
        }
        emit(
          AlertsLoaded(
            alerts: page.items,
            cursor: page.cursor,
            hasNext: page.hasNext,
          ),
        );
      },
    );
  }

  @override
  Future<void> close() async {
    await _wsSub?.cancel();
    _wsSub = null;
    return super.close();
  }
}
