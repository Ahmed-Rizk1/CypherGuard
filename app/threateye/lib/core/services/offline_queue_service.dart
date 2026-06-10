import 'dart:async';
import 'dart:convert';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:threateye/core/services/logger_service.dart';
import 'package:threateye/features/decision/data/datasources/decision_remote_data_source.dart';

/// A single queued analyst decision that could not be delivered immediately
/// because the device was offline at submission time.
class PendingDecision {
  final String  alertId;
  final String  action;
  final String? note;

  /// Wall-clock time (UTC) when the analyst submitted the decision.
  final DateTime queuedAt;

  const PendingDecision({
    required this.alertId,
    required this.action,
    required this.queuedAt,
    this.note,
  });

  // ── Serialisation ──────────────────────────────────────────────────────────

  Map<String, dynamic> toJson() => {
        'alertId':  alertId,
        'action':   action,
        'note':     note,
        'queuedAt': queuedAt.toIso8601String(),
      };

  factory PendingDecision.fromJson(Map<String, dynamic> json) =>
      PendingDecision(
        alertId:  json['alertId']  as String,
        action:   json['action']   as String,
        note:     json['note']     as String?,
        queuedAt: DateTime.parse(json['queuedAt'] as String),
      );
}

/// Manages an offline action queue for [SubmitDecisionUseCase].
///
/// ## Behaviour
/// 1. When the analyst submits a decision and the network is unavailable,
///    the caller should invoke [enqueue] to persist the payload locally.
/// 2. This service listens to [Connectivity.onConnectivityChanged]. When any
///    non-[ConnectivityResult.none] result is observed, [_flush] is called.
/// 3. [_flush] drains the queue in FIFO order, retrying each item against
///    [DecisionRemoteDataSource.submitDecision]. Successfully submitted items
///    are removed from the queue; failed items are left for the next flush.
/// 4. The queue is durable — it survives app restarts via [SharedPreferences].
///
/// ## Registration
/// Register as a lazy singleton in the DI container and call [init] once
/// during app start-up (after SharedPreferences is available).
class OfflineQueueService {
  OfflineQueueService(this._dataSource);

  final DecisionRemoteDataSource _dataSource;

  // ── Internal state ─────────────────────────────────────────────────────────

  static const String _kQueueKey = 'offline_decision_queue';

  SharedPreferences? _prefs;
  StreamSubscription<List<ConnectivityResult>>? _connectivitySub;

  /// Guard against concurrent flush attempts.
  bool _isFlushing = false;

  /// When `false`, [_flush] will not run (set during logout to prevent
  /// the queue from firing with a stale session).
  bool _active = true;

  // ── Public API ─────────────────────────────────────────────────────────────

  /// Must be called once after the DI container is ready.
  ///
  /// Loads [SharedPreferences], attaches the connectivity listener, and
  /// triggers an immediate flush in case items queued during a previous
  /// session are still pending.
  Future<void> init() async {
    _prefs = await SharedPreferences.getInstance();
    _startListening();
    // Attempt to flush any decisions left over from a previous session.
    await _flush();
  }

  /// Persists [decision] to the local queue for later delivery.
  ///
  /// Call this when [SubmitDecisionUseCase] returns a [NetworkFailure].
  Future<void> enqueue(PendingDecision decision) async {
    if (_prefs == null) {
      LoggerService.warning('[OfflineQueue] Not initialised — decision lost.');
      return;
    }

    final current = _readQueue();
    current.add(decision);
    await _writeQueue(current);

    LoggerService.info(
      '[OfflineQueue] Enqueued decision for alert ${decision.alertId}. '
      'Queue size: ${current.length}.',
    );
  }

  /// Returns an unmodifiable snapshot of the current queue.
  List<PendingDecision> get pendingDecisions =>
      List.unmodifiable(_readQueue());

  /// Returns the number of decisions waiting to be delivered.
  int get pendingCount => _readQueue().length;

  /// Pause auto-flush (call during logout before tokens are wiped).
  void pause() {
    _active = false;
    LoggerService.info('[OfflineQueue] Paused.');
  }

  /// Resume auto-flush (call after a successful login).
  void resume() {
    _active = true;
    LoggerService.info('[OfflineQueue] Resumed.');
    // Attempt an immediate flush in case items accumulated while paused.
    _flush();
  }

  /// Discards the entire queue without submitting.
  ///
  /// Call this on logout to prevent a new user's session from inheriting
  /// decisions made by the previous analyst.
  Future<void> clear() async {
    await _writeQueue([]);
    LoggerService.info('[OfflineQueue] Queue cleared.');
  }

  /// Cancels the connectivity listener and releases resources.
  Future<void> dispose() async {
    await _connectivitySub?.cancel();
    _connectivitySub = null;
    LoggerService.info('[OfflineQueue] Disposed.');
  }

  // ── Connectivity listener ──────────────────────────────────────────────────

  void _startListening() {
    _connectivitySub = Connectivity()
        .onConnectivityChanged
        .listen(_onConnectivityChanged);
    LoggerService.info('[OfflineQueue] Connectivity listener active.');
  }

  void _onConnectivityChanged(List<ConnectivityResult> results) {
    final isOnline = results.any((r) => r != ConnectivityResult.none);
    if (isOnline) {
      LoggerService.info('[OfflineQueue] Network restored — flushing queue.');
      _flush();
    }
  }

  // ── Flush logic ────────────────────────────────────────────────────────────

  /// Drains the queue, POSTing each decision to the server.
  ///
  /// Items that succeed are removed immediately; items that fail on a
  /// non-network error are also removed (they are malformed and retrying
  /// them will never help). Network errors leave the item in place so it
  /// can be retried on the next connectivity event.
  Future<void> _flush() async {
    if (!_active || _isFlushing) return;
    if (_prefs == null)           return;

    final queue = _readQueue();
    if (queue.isEmpty) return;

    _isFlushing = true;
    LoggerService.info('[OfflineQueue] Flushing ${queue.length} pending decision(s).');

    // Work on a mutable copy; rebuild survivors after the loop.
    final survivors = <PendingDecision>[];

    for (final decision in queue) {
      if (!_active) {
        // Logout fired mid-flush — stop immediately; keep remaining items.
        survivors.addAll(queue.sublist(queue.indexOf(decision)));
        break;
      }

      try {
        await _dataSource.submitDecision(
          alertId: decision.alertId,
          action:  decision.action,
          note:    decision.note,
        );
        LoggerService.info(
          '[OfflineQueue] Flushed decision for alert ${decision.alertId}.',
        );
      } on Exception catch (e) {
        // Distinguish network failures (keep) from server errors (drop).
        final msg = e.toString().toLowerCase();
        final isNetworkError = msg.contains('socketexception') ||
            msg.contains('connection') ||
            msg.contains('timeout') ||
            msg.contains('networkexception');

        if (isNetworkError) {
          LoggerService.warning(
            '[OfflineQueue] Network error — keeping item for next retry.',
          );
          survivors.add(decision);
        } else {
          LoggerService.error(
            '[OfflineQueue] Server rejected decision '
            '(alert ${decision.alertId}) — dropping: $e',
          );
          // Non-network errors (e.g. 400 Bad Request) are not retriable.
        }
      }
    }

    await _writeQueue(survivors);
    _isFlushing = false;

    LoggerService.info(
      '[OfflineQueue] Flush complete. '
      '${survivors.length} item(s) remain.',
    );
  }

  // ── SharedPreferences helpers ──────────────────────────────────────────────

  List<PendingDecision> _readQueue() {
    final raw = _prefs?.getString(_kQueueKey);
    if (raw == null || raw.isEmpty) return [];

    try {
      final list = jsonDecode(raw) as List<dynamic>;
      return list
          .map((e) => PendingDecision.fromJson(e as Map<String, dynamic>))
          .toList();
    } catch (e) {
      LoggerService.error('[OfflineQueue] Failed to deserialise queue: $e');
      return [];
    }
  }

  Future<void> _writeQueue(List<PendingDecision> queue) async {
    final encoded = jsonEncode(queue.map((d) => d.toJson()).toList());
    await _prefs?.setString(_kQueueKey, encoded);
  }
}
