import 'package:dartz/dartz.dart';
import 'package:threateye/core/error/failures.dart';
import 'package:threateye/core/network/paginated_response.dart';
import '../entities/attack_alert_entity.dart';

abstract class AlertsRepository {
  /// Fetches a paginated list of alerts with optional filters.
  ///
  /// Pass [cursor] from the previous [PaginatedResponse.cursor] to load the
  /// next page. Omit it (or pass `null`) for the first page.
  Future<Either<Failure, PaginatedResponse<AttackAlertEntity>>> getAlerts({
    String? severity,
    String? status,
    String? cursor,
  });

  /// Fetches a single alert by [id].
  ///
  /// Returns [NotFoundFailure] if the alert no longer exists (404).
  Future<Either<Failure, AttackAlertEntity>> getAlertById(String id);

  /// Sends a PATCH request to update the alert's [status].
  ///
  /// Returns the updated entity on success.
  Future<Either<Failure, AttackAlertEntity>> updateAlertStatus(
    String id,
    String status,
  );
}
