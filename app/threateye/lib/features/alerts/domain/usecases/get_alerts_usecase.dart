import 'package:dartz/dartz.dart';
import 'package:threateye/core/error/failures.dart';
import 'package:threateye/core/network/paginated_response.dart';
import '../entities/attack_alert_entity.dart';
import '../repositories/alerts_repository.dart';

class GetAlertsUseCase {
  final AlertsRepository repository;

  GetAlertsUseCase(this.repository);

  /// Fetches a page of alerts with optional filters.
  ///
  /// [severity] and [status] filter values should match the API enum strings
  /// (e.g., `'critical'`, `'resolved'`). Pass `null` to omit the filter.
  /// [cursor] is the opaque pagination cursor from the previous response.
  Future<Either<Failure, PaginatedResponse<AttackAlertEntity>>> call({
    String? severity,
    String? status,
    String? cursor,
  }) =>
      repository.getAlerts(
        severity: severity,
        status:   status,
        cursor:   cursor,
      );
}
