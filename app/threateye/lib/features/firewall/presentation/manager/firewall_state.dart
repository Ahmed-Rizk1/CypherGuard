import 'package:threateye/features/firewall/domain/entities/blocked_ip_entity.dart';

// ─── Base ───────────────────────────────────────────────────────────────────

abstract class FirewallState {}

// ─── List states ─────────────────────────────────────────────────────────────

class FirewallInitial extends FirewallState {}

/// First-page load in progress (show skeleton).
class FirewallLoading extends FirewallState {}

/// At least one page of blocked IPs loaded successfully.
class FirewallLoaded extends FirewallState {
  final List<BlockedIpEntity> blockedIps;
  final String?               cursor;
  final bool                  hasNext;

  /// True while a `loadMore()` is in-flight — scroll guard.
  final bool                  isLoadingMore;

  FirewallLoaded({
    required this.blockedIps,
    required this.cursor,
    required this.hasNext,
    this.isLoadingMore = false,
  });

  FirewallLoaded copyWith({
    List<BlockedIpEntity>? blockedIps,
    String?                cursor,
    bool?                  hasNext,
    bool?                  isLoadingMore,
  }) =>
      FirewallLoaded(
        blockedIps:    blockedIps    ?? this.blockedIps,
        cursor:        cursor        ?? this.cursor,
        hasNext:       hasNext       ?? this.hasNext,
        isLoadingMore: isLoadingMore ?? this.isLoadingMore,
      );
}

/// Non-recoverable error loading the list.
class FirewallError extends FirewallState {
  final String message;
  FirewallError(this.message);
}

// ─── Action states (block / unblock) ─────────────────────────────────────────

/// A POST /firewall/block or DELETE /firewall/block/{ip} is in-flight.
///
/// [targetIp] identifies which row triggered the action so the UI can show a
/// per-row loading indicator rather than disabling the entire screen.
class FirewallActionInProgress extends FirewallState {
  final String targetIp;
  FirewallActionInProgress(this.targetIp);
}

/// Block or unblock succeeded.
class FirewallActionSuccess extends FirewallState {
  final String message;
  FirewallActionSuccess(this.message);
}

/// Block or unblock failed.
class FirewallActionError extends FirewallState {
  final String message;
  FirewallActionError(this.message);
}
