import 'dart:async';
import 'dart:convert';

import 'package:web_socket_channel/web_socket_channel.dart';

import 'logger_service.dart';
import 'secure_storage_service.dart';

/// Manages a single WebSocket connection to the SOC backend.
///
/// Features:
/// - Reads the `access_token` from [SecureStorageService] at connect time.
/// - Heartbeat: sends `{"type":"ping"}` every 30 s.
/// - Exponential backoff reconnection (1 s → 2 s → 4 s → … max 30 s).
/// - Exposes a broadcast [messageStream] that other services / cubits can
///   subscribe to without owning the connection lifecycle.
/// - Fully memory-safe: every Timer and StreamSubscription is cancelled in
///   [dispose].
class WebSocketManagerService {
  WebSocketManagerService(this._storage);

  final SecureStorageService _storage;

  static const String _wsBaseUrl = String.fromEnvironment(
    'WS_BASE_URL',
    defaultValue: 'ws://16.171.61.103:8005/ws/mobile',
  );
  static const Duration _heartbeatInterval = Duration(seconds: 30);
  static const Duration _maxBackoff        = Duration(seconds: 30);

  // ── State ──────────────────────────────────────────────────────────────────
  WebSocketChannel?         _channel;
  StreamSubscription<dynamic>? _channelSub;
  Timer?                    _heartbeatTimer;
  Timer?                    _reconnectTimer;

  /// Current reconnect delay. Doubles on every failed attempt, capped at 30 s.
  Duration _backoff = const Duration(seconds: 1);

  bool _disposed    = false;
  bool _intentional = false; // true when disconnect() is called deliberately

  // ── Public stream ──────────────────────────────────────────────────────────

  /// Broadcast stream of decoded JSON messages from the server.
  ///
  /// Downstream listeners (e.g. [AlertsCubit]) subscribe to this stream.
  /// The stream never closes unless [dispose] is called — reconnects are
  /// transparent to subscribers.
  Stream<Map<String, dynamic>> get messageStream => _controller.stream;

  final StreamController<Map<String, dynamic>> _controller =
      StreamController<Map<String, dynamic>>.broadcast();

  // ── Public API ─────────────────────────────────────────────────────────────

  /// Opens the WebSocket connection.
  ///
  /// Safe to call multiple times — subsequent calls while already connected
  /// are no-ops. Call [disconnect] first if you need to re-connect with a
  /// fresh token.
  Future<void> connect() async {
    if (_disposed) return;
    if (_channel != null) return; // already connected

    final token = await _storage.read('access_token');
    if (token == null || token.isEmpty) {
      LoggerService.warning(
        '[WebSocket] No access_token found — connection skipped.',
      );
      return;
    }

    final uri = Uri.parse('$_wsBaseUrl?token=$token');
    LoggerService.info('[WebSocket] Connecting → $uri');

    try {
      _channel = WebSocketChannel.connect(uri);
      await _channel!.ready;

      _backoff = const Duration(seconds: 1); // reset on successful connect
      LoggerService.info('[WebSocket] Connected.');

      _startHeartbeat();
      _listenToChannel();
    } catch (e) {
      LoggerService.error('[WebSocket] Connection failed: $e');
      _channel = null;
      _scheduleReconnect();
    }
  }

  /// Deliberately closes the connection without scheduling a reconnect.
  ///
  /// Call this on logout so we do not attempt to reconnect with a stale token.
  void disconnect() {
    _intentional = true;
    _cleanupConnection();
    LoggerService.info('[WebSocket] Disconnected (intentional).');
  }

  /// Releases all resources. Must be called when the service is no longer
  /// needed (registered as singleton — call from app lifecycle observer).
  void dispose() {
    _disposed = true;
    _intentional = true;
    _cleanupConnection();
    _controller.close();
    LoggerService.info('[WebSocket] Disposed.');
  }

  // ── Internal ───────────────────────────────────────────────────────────────

  void _listenToChannel() {
    _channelSub = _channel!.stream.listen(
      _onMessage,
      onError: _onError,
      onDone:  _onDone,
      cancelOnError: false,
    );
  }

  void _onMessage(dynamic raw) {
    try {
      final decoded = jsonDecode(raw as String) as Map<String, dynamic>;

      // Silently swallow pong frames — no need to forward them downstream.
      if (decoded['type'] == 'pong') return;

      _controller.add(decoded);
    } catch (e) {
      LoggerService.warning('[WebSocket] Failed to decode message: $e');
    }
  }

  void _onError(Object error) {
    LoggerService.error('[WebSocket] Stream error: $error');
    _cleanupConnection();
    if (!_intentional) _scheduleReconnect();
  }

  void _onDone() {
    LoggerService.info('[WebSocket] Stream closed by server.');
    _cleanupConnection();
    if (!_intentional) _scheduleReconnect();
  }

  void _startHeartbeat() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = Timer.periodic(_heartbeatInterval, (_) {
      _sendPing();
    });
  }

  void _sendPing() {
    if (_channel == null) return;
    try {
      _channel!.sink.add(jsonEncode({'type': 'ping'}));
      LoggerService.info('[WebSocket] Ping sent.');
    } catch (e) {
      LoggerService.warning('[WebSocket] Failed to send ping: $e');
    }
  }

  /// Schedules a reconnect attempt after the current backoff delay.
  ///
  /// Doubles [_backoff] after each call, capped at [_maxBackoff].
  void _scheduleReconnect() {
    if (_disposed || _intentional) return;

    _reconnectTimer?.cancel();
    LoggerService.info(
      '[WebSocket] Reconnecting in ${_backoff.inSeconds} s …',
    );

    _reconnectTimer = Timer(_backoff, () async {
      if (_disposed || _intentional) return;
      // Double the backoff, capped at max.
      _backoff = Duration(
        seconds: (_backoff.inSeconds * 2).clamp(1, _maxBackoff.inSeconds),
      );
      _intentional = false;
      await connect();
    });
  }

  void _cleanupConnection() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = null;

    _reconnectTimer?.cancel();
    _reconnectTimer = null;

    _channelSub?.cancel();
    _channelSub = null;

    _channel?.sink.close();
    _channel = null;
  }
}
