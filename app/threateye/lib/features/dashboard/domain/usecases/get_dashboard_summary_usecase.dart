import 'package:dartz/dartz.dart';
import 'package:threateye/core/error/failures.dart';
import '../entities/dashboard_summary_entity.dart';
import '../repositories/dashboard_repository.dart';

class GetDashboardSummaryUseCase {
  final DashboardRepository repository;

  GetDashboardSummaryUseCase(this.repository);

  /// Returns the dashboard summary or a [Failure].
  Future<Either<Failure, DashboardSummaryEntity>> call() =>
      repository.getDashboardSummary();
}
