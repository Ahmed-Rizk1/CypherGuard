import 'package:dartz/dartz.dart';
import 'package:threateye/core/error/failures.dart';
import '../entities/decision_entity.dart';
import '../repositories/decision_repository.dart';

/// Submits an analyst decision (APPROVE | REJECT | ESCALATE) on an alert.
///
/// Usage:
/// ```dart
/// final result = await submitDecisionUseCase(
///   alertId: alert.id,
///   action:  DecisionAction.approve.toApiString(),
///   note:    'Confirmed as expected traffic.',
/// );
/// ```
class SubmitDecisionUseCase {
  final DecisionRepository repository;

  SubmitDecisionUseCase(this.repository);

  Future<Either<Failure, DecisionEntity>> call({
    required String alertId,
    required String action,
    String? note,
  }) =>
      repository.submitDecision(
        alertId: alertId,
        action:  action,
        note:    note,
      );
}
