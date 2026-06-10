import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:threateye/features/decision/domain/entities/decision_entity.dart';
import 'package:threateye/features/decision/presentation/manager/decision_cubit.dart';
import 'package:threateye/features/decision/presentation/manager/decision_state.dart';
import 'package:threateye/features/firewall/presentation/manager/firewall_cubit.dart';
import 'package:threateye/features/firewall/presentation/manager/firewall_state.dart';
import 'package:threateye/injection_container.dart';
import '../../domain/entities/attack_alert_entity.dart';
import '../manager/alerts_cubit.dart';
import '../manager/alerts_state.dart';
import '../wedgets/alert_details_card.dart';
import '../wedgets/alert_hero_header.dart';
import '../wedgets/alert_quick_actions.dart';
import '../wedgets/alert_severity_utils.dart';
import '../wedgets/incident_status_card.dart';
import '../wedgets/recommended_response_card.dart';

class AlertDetailPage extends StatelessWidget {
  const AlertDetailPage({super.key});

  @override
  Widget build(BuildContext context) {
    final args = ModalRoute.of(context)?.settings.arguments;
    if (args == null || args is! AttackAlertEntity) {
      return Scaffold(
        appBar: AppBar(title: const Text('Alert Details')),
        body: const Center(child: Text('Alert not found.')),
      );
    }

    return MultiBlocProvider(
      // Each cubit is factory-registered — a fresh instance is scoped to this page.
      providers: [
        BlocProvider<AlertsCubit>(
          create: (_) => sl<AlertsCubit>(),
        ),
        BlocProvider<DecisionCubit>(
          create: (_) => sl<DecisionCubit>(),
        ),
        BlocProvider<FirewallCubit>(
          create: (_) => sl<FirewallCubit>(),
        ),
      ],
      child: _AlertDetailBody(initialAlert: args),
    );
  }
}

// ─── Body ──────────────────────────────────────────────────────────────────

class _AlertDetailBody extends StatefulWidget {
  final AttackAlertEntity initialAlert;
  const _AlertDetailBody({required this.initialAlert});

  @override
  State<_AlertDetailBody> createState() => _AlertDetailBodyState();
}

class _AlertDetailBodyState extends State<_AlertDetailBody> {
  late String _incidentStatus;

  @override
  void initState() {
    super.initState();
    _incidentStatus = widget.initialAlert.status;
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
        behavior: SnackBarBehavior.floating,
        margin: const EdgeInsets.all(14),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        duration: const Duration(seconds: 2),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return BlocConsumer<AlertsCubit, AlertsState>(
      listener: (context, state) {
        if (state is AlertActionSuccess) {
          setState(() => _incidentStatus = state.updatedAlert.status);
          _showSnackBar(
            'Status updated to "${state.updatedAlert.status}".',
            const Color(0xFF22C55E),
            Icons.check_circle_rounded,
          );
        } else if (state is AlertActionError) {
          _showSnackBar(
            state.message,
            const Color(0xFFEF4444),
            Icons.error_outline_rounded,
          );
        } else if (state is AlertDetailNotFound) {
          _showSnackBar(
            state.message,
            Colors.blueGrey,
            Icons.warning_amber_rounded,
          );
        }
      },
      builder: (context, alertsState) {
        // Also listen to DecisionCubit & FirewallCubit for cross-cubit side-effects.
        return BlocListener<DecisionCubit, DecisionState>(
          listener: (context, decisionState) {
            if (decisionState is DecisionActionSuccess) {
              _showSnackBar(
                'Escalated: decision #${decisionState.decision.id} recorded.',
                const Color(0xFFF97316),
                Icons.arrow_circle_up_rounded,
              );
            } else if (decisionState is DecisionActionError) {
              _showSnackBar(
                decisionState.message,
                const Color(0xFFEF4444),
                Icons.error_outline_rounded,
              );
            }
          },
          child: BlocListener<FirewallCubit, FirewallState>(
            listener: (context, firewallState) {
              if (firewallState is FirewallActionSuccess) {
                _showSnackBar(
                  firewallState.message,
                  const Color(0xFF22C55E),
                  Icons.shield_rounded,
                );
              } else if (firewallState is FirewallActionError) {
                _showSnackBar(
                  firewallState.message,
                  const Color(0xFFEF4444),
                  Icons.error_outline_rounded,
                );
              }
            },
            child: _buildBody(context, alertsState),
          ),
        );
      },
    );
  }

  Widget _buildBody(BuildContext context, AlertsState alertsState) {
        // Resolve the "current" alert: prefer the successfully updated one.
        final alert = (alertsState is AlertActionSuccess)
            ? alertsState.updatedAlert
            : (alertsState is AlertActionInProgress)
                // ignore: unnecessary_cast — alertsState.alert is `dynamic` by design (avoids circular import)
                ? alertsState.alert as AttackAlertEntity
                : widget.initialAlert;

        // True while an alerts PATCH is in-flight → disables action buttons.
        final isAlertActionInProgress = alertsState is AlertActionInProgress;

        // True while a decision submission is in-flight.
        final decisionState   = context.watch<DecisionCubit>().state;
        final isDecisionInProgress = decisionState is DecisionActionInProgress;

        // True while a firewall block/unblock is in-flight.
        final firewallState   = context.watch<FirewallCubit>().state;
        final isFirewallInProgress = firewallState is FirewallActionInProgress;

        // Master guard: disable ALL action buttons if ANY action is in-flight.
        final isActionInProgress =
            isAlertActionInProgress || isDecisionInProgress || isFirewallInProgress;

        // 404 case: show a clean not-found screen (Tech Lead constraint).
        if (alertsState is AlertDetailNotFound) {
          return Scaffold(
            appBar: AppBar(title: const Text('Alert Details')),
            body: Center(
              child: Column(

                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(
                    Icons.search_off_rounded,
                    size: 56,
                    color: Colors.blueGrey,
                  ),
                  const SizedBox(height: 16),
                  Text(
                    // ignore: unnecessary_cast — type already narrowed by is-check on line 184
                    (alertsState as AlertDetailNotFound).message,
                    style: const TextStyle(
                      fontSize: 16,
                      color: Colors.blueGrey,
                      fontWeight: FontWeight.w500,
                    ),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 24),
                  ElevatedButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Go Back'),
                  ),
                ],
              ),
            ),
          );
        }

        final severityColor = AlertSeverityUtils.severityColor(alert.severity);

        return Scaffold(
          appBar: AppBar(
            title: const Text(
              'Alert Details',
              style: TextStyle(fontWeight: FontWeight.w700),
            ),
            leading: BackButton(onPressed: () => Navigator.pop(context)),
            backgroundColor: severityColor.withValues(alpha: 0.05),
            surfaceTintColor: severityColor,
            bottom: PreferredSize(
              preferredSize: const Size.fromHeight(2),
              child: Container(
                height: 2,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [severityColor, severityColor.withValues(alpha: 0)],
                  ),
                ),
              ),
            ),
          ),
          body: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 28),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                AlertHeroHeader(alert: alert, severityColor: severityColor),
                const SizedBox(height: 24),

                AlertDetailsCard(
                  alert: alert,
                  severityColor: severityColor,
                  onShowSnackBar: _showSnackBar,
                ),
                const SizedBox(height: 24),

                IncidentStatusCard(
                  incidentStatus: _incidentStatus,
                  onStatusChanged: (s) => setState(() => _incidentStatus = s),
                ),
                const SizedBox(height: 24),

                RecommendedResponseCard(attackType: alert.attackType),
                const SizedBox(height: 24),

                // ── Analyst Quick Actions ─────────────────────────────────────
                //
                // All three action cubits share the master [isActionInProgress]
                // guard — no duplicate submissions are possible.
                AlertQuickActions(
                  isLoading: isActionInProgress,
                  onMarkResolved: isActionInProgress
                      ? null
                      : () {
                          setState(() => _incidentStatus = 'resolved');
                          context.read<AlertsCubit>().updateStatus(
                                id:        alert.id,
                                newStatus: 'resolved',
                                alert:     alert,
                              );
                        },
                  // Escalate now also submits a formal Decision record (POST /v1/mobile/decision)
                  onEscalate: isActionInProgress
                      ? null
                      : () {
                          setState(() => _incidentStatus = 'investigating');
                          // Update alert status to investigating
                          context.read<AlertsCubit>().updateStatus(
                                id:        alert.id,
                                newStatus: 'investigating',
                                alert:     alert,
                              );
                          // Submit a formal ESCALATE decision record
                          context.read<DecisionCubit>().submitDecision(
                                alertId: alert.id,
                                action:  DecisionAction.escalate.toApiString(),
                                note:    'Escalated from mobile SOC client.',
                              );
                        },
                  onIgnore: isActionInProgress
                      ? null
                      : () {
                          context.read<AlertsCubit>().updateStatus(
                                id:        alert.id,
                                newStatus: 'suppressed',
                                alert:     alert,
                              );
                        },
                ),
                const SizedBox(height: 16),

                // ── Block Source IP ───────────────────────────────────────────
                //
                // Directly submits a firewall block for the alert's source IP.
                // Disabled while any action is in-flight (master guard).
                if (alert.sourceIp.isNotEmpty)
                  _BlockSourceIpButton(
                    ipAddress:   alert.sourceIp,
                    isDisabled:  isActionInProgress,
                    isActing:    isFirewallInProgress,
                    onBlock: () => context.read<FirewallCubit>().blockIp(
                      ipAddress: alert.sourceIp,
                      reason:    'Blocked from Alert #${alert.id} (${alert.attackType})',
                    ),
                  ),
              ],
            ),
          ),
        );
  }
}

// ── Block Source IP Button ────────────────────────────────────────────────────

class _BlockSourceIpButton extends StatelessWidget {
  final String       ipAddress;
  final bool         isDisabled;
  final bool         isActing;
  final VoidCallback onBlock;

  const _BlockSourceIpButton({
    required this.ipAddress,
    required this.isDisabled,
    required this.isActing,
    required this.onBlock,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: isDisabled
                ? const Color(0xFF374151)
                : const Color(0xFFEF4444).withValues(alpha: 0.5),
          ),
        ),
        child: Material(
          color:        Colors.transparent,
          borderRadius: BorderRadius.circular(14),
          child: InkWell(
            onTap:        isDisabled ? null : onBlock,
            borderRadius: BorderRadius.circular(14),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 16),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  if (isActing)
                    const SizedBox(
                      width: 18, height: 18,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color:       Color(0xFFEF4444),
                      ),
                    )
                  else
                    Icon(
                      Icons.block_rounded,
                      size:  18,
                      color: isDisabled
                          ? const Color(0xFF374151)
                          : const Color(0xFFEF4444),
                    ),
                  const SizedBox(width: 10),
                  Text(
                    isActing
                        ? 'Blocking $ipAddress…'
                        : 'Block Source IP  $ipAddress',
                    style: TextStyle(
                      color: isDisabled
                          ? const Color(0xFF374151)
                          : const Color(0xFFEF4444),
                      fontWeight: FontWeight.w700,
                      fontSize:   14,
                      fontFamily: 'monospace',
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
