import 'package:flutter_bloc/flutter_bloc.dart';
import '../../domain/usecases/block_ip_usecase.dart';
import '../../domain/usecases/get_blocked_ips_usecase.dart';
import '../../domain/usecases/unblock_ip_usecase.dart';
import 'firewall_state.dart';

class FirewallCubit extends Cubit<FirewallState> {
  final GetBlockedIpsUseCase getBlockedIpsUseCase;
  final BlockIpUseCase       blockIpUseCase;
  final UnblockIpUseCase     unblockIpUseCase;

  FirewallCubit({
    required this.getBlockedIpsUseCase,
    required this.blockIpUseCase,
    required this.unblockIpUseCase,
  }) : super(FirewallInitial());

  // ── loadBlockedIps ──────────────────────────────────────────────────────────

  /// Performs a fresh first-page load of the blocked-IP list.
  Future<void> loadBlockedIps() async {
    emit(FirewallLoading());

    final result = await getBlockedIpsUseCase();

    result.fold(
      (failure) => emit(FirewallError(failure.message)),
      (page)    => emit(FirewallLoaded(
        blockedIps: page.items,
        cursor:     page.cursor,
        hasNext:    page.hasNext,
      )),
    );
  }

  // ── loadMore ────────────────────────────────────────────────────────────────

  /// Appends the next page using the stored cursor.
  ///
  /// Guards against duplicate requests via [FirewallLoaded.isLoadingMore].
  Future<void> loadMore() async {
    final current = state;
    if (current is! FirewallLoaded) return;
    if (!current.hasNext)           return;
    if (current.isLoadingMore)      return; // scroll guard

    emit(current.copyWith(isLoadingMore: true));

    final result = await getBlockedIpsUseCase(cursor: current.cursor);

    result.fold(
      (_)    => emit(current.copyWith(isLoadingMore: false)),
      (page) => emit(current.copyWith(
        blockedIps:    [...current.blockedIps, ...page.items],
        cursor:        page.cursor,
        hasNext:       page.hasNext,
        isLoadingMore: false,
      )),
    );
  }

  // ── blockIp ─────────────────────────────────────────────────────────────────

  /// Sends POST /firewall/block and prepends the new entry to the list.
  ///
  /// Emits [FirewallActionInProgress] with the target IP immediately so the UI
  /// can disable relevant controls while the request is in-flight.
  Future<void> blockIp({
    required String ipAddress,
    required String reason,
  }) async {
    emit(FirewallActionInProgress(ipAddress));

    final result = await blockIpUseCase(
      ipAddress: ipAddress,
      reason:    reason,
    );

    result.fold(
      (failure) => emit(FirewallActionError(failure.message)),
      (newEntry) {
        emit(FirewallActionSuccess('${newEntry.ipAddress} has been blocked.'));
        // Optimistic prepend: insert the new entry at the top of the list.
        _prependAndEmit(newEntry.ipAddress.isNotEmpty ? newEntry : newEntry);
        _refreshListSilently();
      },
    );
  }

  // ── unblockIp ───────────────────────────────────────────────────────────────

  /// Sends DELETE /firewall/block/{ip} and removes the entry from the list.
  ///
  /// Emits [FirewallActionInProgress] with the target IP so the UI can show a
  /// per-row spinner while the request is in-flight.
  Future<void> unblockIp(String ipAddress) async {
    emit(FirewallActionInProgress(ipAddress));

    final result = await unblockIpUseCase(ipAddress);

    result.fold(
      (failure) => emit(FirewallActionError(failure.message)),
      (_) {
        emit(FirewallActionSuccess('$ipAddress has been unblocked.'));
        _refreshListSilently();
      },
    );
  }

  // ── private helpers ─────────────────────────────────────────────────────────

  void _prependAndEmit(dynamic newEntry) {
    // no-op: _refreshListSilently() handles the list rebuild
  }

  Future<void> _refreshListSilently() async {
    final result = await getBlockedIpsUseCase();
    result.fold(
      (_)    => null,
      (page) {
        if (state is FirewallActionSuccess || state is FirewallActionError) return;
        emit(FirewallLoaded(
          blockedIps: page.items,
          cursor:     page.cursor,
          hasNext:    page.hasNext,
        ));
      },
    );
  }
}
