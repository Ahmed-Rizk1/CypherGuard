import 'package:dartz/dartz.dart';
import 'package:threateye/core/error/failures.dart';
import '../entities/dashboard_summary_entity.dart';

abstract class DashboardRepository {
  /// Returns [DashboardSummaryEntity] on success or a [Failure] on error.
  Future<Either<Failure, DashboardSummaryEntity>> getDashboardSummary();
}
