import 'package:dartz/dartz.dart';
import 'package:threateye/core/error/failures.dart';
import 'package:threateye/core/network/paginated_response.dart';
import '../entities/decision_entity.dart';
import '../repositories/decision_repository.dart';

/// Retrieves a cursor-paginated page of SOC decision history.
class GetDecisionHistoryUseCase {
  final DecisionRepository repository;

  GetDecisionHistoryUseCase(this.repository);

  Future<Either<Failure, PaginatedResponse<DecisionEntity>>> call({
    String? cursor,
  }) =>
      repository.getDecisionHistory(cursor: cursor);
}
