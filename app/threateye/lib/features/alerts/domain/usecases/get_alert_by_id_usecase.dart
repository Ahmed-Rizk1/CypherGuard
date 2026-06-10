import 'package:dartz/dartz.dart';
import 'package:threateye/core/error/failures.dart';
import '../entities/attack_alert_entity.dart';
import '../repositories/alerts_repository.dart';

/// Fetches a single alert by ID.
///
/// Returns [NotFoundFailure] when the server returns 404 — the caller
/// (typically [AlertsCubit]) should emit a distinct state so the UI can
/// show "This alert no longer exists" instead of a generic error banner.
class GetAlertByIdUseCase {
  final AlertsRepository repository;

  GetAlertByIdUseCase(this.repository);

  Future<Either<Failure, AttackAlertEntity>> call(String id) =>
      repository.getAlertById(id);
}
