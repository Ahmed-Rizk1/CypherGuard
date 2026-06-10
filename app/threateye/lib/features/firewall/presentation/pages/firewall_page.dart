import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:threateye/injection_container.dart';
import '../../domain/entities/blocked_ip_entity.dart';
import '../manager/firewall_cubit.dart';
import '../manager/firewall_state.dart';

class FirewallPage extends StatelessWidget {
  const FirewallPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => sl<FirewallCubit>()..loadBlockedIps(),
      child: const _FirewallView(),
    );
  }
}

// ── Inner stateful view ──────────────────────────────────────────────────────

class _FirewallView extends StatefulWidget {
  const _FirewallView();

  @override
  State<_FirewallView> createState() => _FirewallViewState();
}

class _FirewallViewState extends State<_FirewallView> {
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
      context.read<FirewallCubit>().loadMore();
    }
  }

  void _showSnackBar(String message, Color color, IconData icon) {
    ScaffoldMessenger.of(context).clearSnackBars();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            Icon(icon, color: Colors.white, size: 18),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                message,
                style: const TextStyle(fontWeight: FontWeight.w500),
              ),
            ),
          ],
        ),
        backgroundColor: color,
        behavior:  SnackBarBehavior.floating,
        margin:    const EdgeInsets.all(14),
        shape:     RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        duration:  const Duration(seconds: 3),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0E1A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0D1120),
        surfaceTintColor: Colors.transparent,
        title: const Text(
          'Firewall Management',
          style: TextStyle(
            fontWeight: FontWeight.w700,
            color: Colors.white,
            fontSize: 18,
          ),
        ),
        iconTheme: const IconThemeData(color: Colors.white),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded, color: Color(0xFF6366F1)),
            tooltip: 'Refresh',
            onPressed: () => context.read<FirewallCubit>().loadBlockedIps(),
          ),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(1),
          child: Container(
            height: 1,
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                colors: [Color(0xFFEF4444), Color(0x00EF4444)],
              ),
            ),
          ),
        ),
      ),
      // ── Floating Action Button — Block IP ──────────────────────────────────
      floatingActionButton: BlocBuilder<FirewallCubit, FirewallState>(
        builder: (context, state) {
          final isActing = state is FirewallActionInProgress;
          return FloatingActionButton.extended(
            onPressed: isActing
                ? null
                : () => _showBlockIpDialog(context),
            icon: isActing
                ? const SizedBox(
                    width: 18, height: 18,
                    child: CircularProgressIndicator(
                      strokeWidth: 2, color: Colors.white,
                    ),
                  )
                : const Icon(Icons.block_rounded),
            label: const Text(
              'Block IP',
              style: TextStyle(fontWeight: FontWeight.w700),
            ),
            backgroundColor: const Color(0xFFEF4444),
            foregroundColor: Colors.white,
          );
        },
      ),
      body: BlocConsumer<FirewallCubit, FirewallState>(
        listener: (context, state) {
          if (state is FirewallActionSuccess) {
            _showSnackBar(
              state.message,
              const Color(0xFF22C55E),
              Icons.check_circle_rounded,
            );
          } else if (state is FirewallActionError) {
            _showSnackBar(
              state.message,
              const Color(0xFFEF4444),
              Icons.error_outline_rounded,
            );
          }
        },
        builder: (context, state) {
          if (state is FirewallLoading) {
            return const _FirewallSkeleton();
          }
          if (state is FirewallLoaded ||
              state is FirewallActionInProgress ||
              state is FirewallActionSuccess ||
              state is FirewallActionError) {
            // Extract the last known loaded state for the list.
            FirewallLoaded? loaded;
            String?         actingIp;

            if (state is FirewallLoaded) {
              loaded = state;
            } else if (state is FirewallActionInProgress) {
              actingIp = state.targetIp;
              // Keep last-known list visible via a listener pattern below.
            }

            if (loaded == null) {
              // Transient action state — show a spinner overlay instead.
              return const Center(
                child: CircularProgressIndicator(color: Color(0xFF6366F1)),
              );
            }

            if (loaded.blockedIps.isEmpty) {
              return const _FirewallEmpty();
            }

            return _FirewallList(
              state:            loaded,
              scrollController: _scrollController,
              actingIp:         actingIp,
              onUnblock: (ip) => context.read<FirewallCubit>().unblockIp(ip),
            );
          }
          if (state is FirewallError) {
            return _FirewallErrorState(
              message:  state.message,
              onRetry: () => context.read<FirewallCubit>().loadBlockedIps(),
            );
          }
          return const SizedBox.shrink();
        },
      ),
    );
  }

  // ── Block IP dialog ─────────────────────────────────────────────────────────

  void _showBlockIpDialog(BuildContext pageContext) {
    final ipController     = TextEditingController();
    final reasonController = TextEditingController();
    final formKey          = GlobalKey<FormState>();

    showDialog<void>(
      context: pageContext,
      builder: (dialogContext) => AlertDialog(
        backgroundColor:  const Color(0xFF111827),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: const Row(
          children: [
            Icon(Icons.block_rounded, color: Color(0xFFEF4444)),
            SizedBox(width: 10),
            Text(
              'Block IP Address',
              style: TextStyle(color: Colors.white, fontWeight: FontWeight.w700),
            ),
          ],
        ),
        content: Form(
          key: formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // IP Address field
              TextFormField(
                controller: ipController,
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  labelText:  'IP Address',
                  labelStyle: const TextStyle(color: Color(0xFF6B7280)),
                  hintText:   '192.168.1.100',
                  hintStyle:  const TextStyle(color: Color(0xFF374151)),
                  prefixIcon: const Icon(Icons.lan_rounded, color: Color(0xFF6B7280)),
                  filled:     true,
                  fillColor:  const Color(0xFF1F2937),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide.none,
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: const BorderSide(color: Color(0xFFEF4444), width: 1.5),
                  ),
                ),
                keyboardType: TextInputType.url,
                inputFormatters: [
                  FilteringTextInputFormatter.allow(RegExp(r'[\d.]')),
                ],
                validator: (v) {
                  if (v == null || v.trim().isEmpty) return 'Required';
                  // Basic IPv4 regex
                  final ipRegex = RegExp(
                    r'^(\d{1,3}\.){3}\d{1,3}$',
                  );
                  if (!ipRegex.hasMatch(v.trim())) return 'Enter a valid IPv4 address';
                  return null;
                },
              ),
              const SizedBox(height: 14),
              // Reason field
              TextFormField(
                controller: reasonController,
                style: const TextStyle(color: Colors.white),
                maxLines: 2,
                decoration: InputDecoration(
                  labelText:  'Reason',
                  labelStyle: const TextStyle(color: Color(0xFF6B7280)),
                  hintText:   'e.g. DDoS source, brute force...',
                  hintStyle:  const TextStyle(color: Color(0xFF374151)),
                  prefixIcon: const Icon(Icons.notes_rounded, color: Color(0xFF6B7280)),
                  filled:     true,
                  fillColor:  const Color(0xFF1F2937),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide.none,
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: const BorderSide(color: Color(0xFFEF4444), width: 1.5),
                  ),
                ),
                validator: (v) =>
                    (v == null || v.trim().isEmpty) ? 'Required' : null,
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Cancel', style: TextStyle(color: Color(0xFF6B7280))),
          ),
          ElevatedButton.icon(
            icon:  const Icon(Icons.block_rounded, size: 18),
            label: const Text('Block', style: TextStyle(fontWeight: FontWeight.w700)),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFFEF4444),
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10),
              ),
            ),
            onPressed: () {
              if (formKey.currentState!.validate()) {
                Navigator.pop(dialogContext);
                pageContext.read<FirewallCubit>().blockIp(
                  ipAddress: ipController.text.trim(),
                  reason:    reasonController.text.trim(),
                );
              }
            },
          ),
        ],
      ),
    );
  }
}

// ── List ─────────────────────────────────────────────────────────────────────

class _FirewallList extends StatelessWidget {
  final FirewallLoaded   state;
  final ScrollController scrollController;
  final String?          actingIp;
  final void Function(String ip) onUnblock;

  const _FirewallList({
    required this.state,
    required this.scrollController,
    required this.onUnblock,
    this.actingIp,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // ── Stats banner ─────────────────────────────────────────────────────
        Container(
          margin: const EdgeInsets.fromLTRB(16, 14, 16, 4),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: [
                const Color(0xFFEF4444).withValues(alpha: 0.12),
                const Color(0xFFEF4444).withValues(alpha: 0.04),
              ],
            ),
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: const Color(0xFFEF4444).withValues(alpha: 0.2)),
          ),
          child: Row(
            children: [
              const Icon(Icons.shield_rounded, color: Color(0xFFEF4444), size: 20),
              const SizedBox(width: 10),
              Text(
                '${state.blockedIps.length} IP${state.blockedIps.length != 1 ? 's' : ''} currently blocked',
                style: const TextStyle(
                  color:      Color(0xFFEF4444),
                  fontWeight: FontWeight.w700,
                  fontSize:   14,
                ),
              ),
            ],
          ),
        ),
        // ── List ─────────────────────────────────────────────────────────────
        Expanded(
          child: ListView.separated(
            controller: scrollController,
            padding: const EdgeInsets.fromLTRB(16, 10, 16, 96), // 96 for FAB clearance
            itemCount: state.blockedIps.length + (state.isLoadingMore ? 1 : 0),
            separatorBuilder: (_, __) => const SizedBox(height: 10),
            itemBuilder: (context, index) {
              if (index == state.blockedIps.length) {
                return const Padding(
                  padding: EdgeInsets.symmetric(vertical: 16),
                  child: Center(
                    child: SizedBox(
                      width: 24, height: 24,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                  ),
                );
              }
              final entry   = state.blockedIps[index];
              final isThisActing = actingIp == entry.ipAddress;
              return _BlockedIpCard(
                entry:       entry,
                isActing:    isThisActing,
                onUnblock:   () => onUnblock(entry.ipAddress),
              );
            },
          ),
        ),
      ],
    );
  }
}

// ── Blocked IP Card ───────────────────────────────────────────────────────────

class _BlockedIpCard extends StatelessWidget {
  final BlockedIpEntity entry;
  final bool            isActing;
  final VoidCallback    onUnblock;

  const _BlockedIpCard({
    required this.entry,
    required this.isActing,
    required this.onUnblock,
  });

  @override
  Widget build(BuildContext context) {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 200),
      decoration: BoxDecoration(
        color: const Color(0xFF111827),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isActing
              ? const Color(0xFFF97316).withValues(alpha: 0.5)
              : const Color(0xFFEF4444).withValues(alpha: 0.2),
          width: isActing ? 1.5 : 1,
        ),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFFEF4444).withValues(alpha: 0.06),
            blurRadius: 10,
            offset: const Offset(0, 3),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          children: [
            // IP icon
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color:        const Color(0xFFEF4444).withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(
                Icons.block_rounded,
                color: Color(0xFFEF4444),
                size:  22,
              ),
            ),
            const SizedBox(width: 12),
            // Info
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    entry.ipAddress,
                    style: const TextStyle(
                      color:      Colors.white,
                      fontWeight: FontWeight.w700,
                      fontSize:   15,
                      fontFamily: 'monospace',
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    entry.reason,
                    style: const TextStyle(
                      color:    Color(0xFF9CA3AF),
                      fontSize: 12,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (entry.blockedBy != null) ...[
                    const SizedBox(height: 3),
                    Row(
                      children: [
                        const Icon(Icons.person_outline_rounded,
                            size: 12, color: Color(0xFF6B7280)),
                        const SizedBox(width: 4),
                        Text(
                          entry.blockedBy!,
                          style: const TextStyle(
                            color: Color(0xFF6B7280), fontSize: 11,
                          ),
                        ),
                        const SizedBox(width: 10),
                        const Icon(Icons.schedule_rounded,
                            size: 12, color: Color(0xFF6B7280)),
                        const SizedBox(width: 4),
                        Text(
                          _formatDate(entry.blockedAt),
                          style: const TextStyle(
                            color: Color(0xFF6B7280), fontSize: 11,
                          ),
                        ),
                      ],
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(width: 8),
            // Unblock button
            if (isActing)
              const SizedBox(
                width: 22, height: 22,
                child: CircularProgressIndicator(
                  strokeWidth: 2, color: Color(0xFFF97316),
                ),
              )
            else
              TextButton(
                onPressed: onUnblock,
                style: TextButton.styleFrom(
                  backgroundColor:  const Color(0xFF22C55E).withValues(alpha: 0.1),
                  foregroundColor:  const Color(0xFF22C55E),
                  padding:          const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10),
                    side: const BorderSide(color: Color(0xFF22C55E), width: 0.8),
                  ),
                ),
                child: const Text(
                  'Unblock',
                  style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
                ),
              ),
          ],
        ),
      ),
    );
  }

  String _formatDate(String iso) {
    try {
      final dt = DateTime.parse(iso).toLocal();
      return '${dt.day.toString().padLeft(2, '0')}/${dt.month.toString().padLeft(2, '0')}';
    } catch (_) {
      return iso;
    }
  }
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

class _FirewallSkeleton extends StatelessWidget {
  const _FirewallSkeleton();

  @override
  Widget build(BuildContext context) {
    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 24),
      itemCount: 7,
      separatorBuilder: (_, __) => const SizedBox(height: 10),
      itemBuilder: (_, __) => Container(
        height: 80,
        decoration: BoxDecoration(
          color:        const Color(0xFF111827),
          borderRadius: BorderRadius.circular(16),
        ),
      ),
    );
  }
}

// ── Empty state ───────────────────────────────────────────────────────────────

class _FirewallEmpty extends StatelessWidget {
  const _FirewallEmpty();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.verified_user_rounded, size: 64, color: Color(0xFF22C55E)),
          SizedBox(height: 16),
          Text(
            'No blocked IPs',
            style: TextStyle(
              color:      Color(0xFF22C55E),
              fontSize:   18,
              fontWeight: FontWeight.w700,
            ),
          ),
          SizedBox(height: 8),
          Text(
            'The firewall blocklist is currently empty.',
            style: TextStyle(color: Color(0xFF6B7280), fontSize: 14),
          ),
        ],
      ),
    );
  }
}

// ── Error state ───────────────────────────────────────────────────────────────

class _FirewallErrorState extends StatelessWidget {
  final String       message;
  final VoidCallback onRetry;

  const _FirewallErrorState({required this.message, required this.onRetry});

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
                backgroundColor: const Color(0xFFEF4444),
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
