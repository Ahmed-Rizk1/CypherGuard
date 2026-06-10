import 'package:dartz/dartz.dart';
import 'package:threateye/core/error/failures.dart';
import '../entities/attack_alert_entity.dart';
import '../repositories/alerts_repository.dart';

/// Sends a PATCH request to update an alert's status.
///
/// Valid [status] values (API enum strings):
///  - `'new'`
///  - `'acknowledged'`
///  - `'investigating'`
///  - `'resolved'`
///  - `'suppressed'`
class UpdateAlertStatusUseCase {
  final AlertsRepository repository;

  UpdateAlertStatusUseCase(this.repository);

  Future<Either<Failure, AttackAlertEntity>> call({
    required String id,
    required String status,
  }) =>
      repository.updateAlertStatus(id, status);
}
