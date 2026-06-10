import 'package:dartz/dartz.dart';
import 'package:threateye/core/error/failures.dart';
import 'package:threateye/core/network/paginated_response.dart';
import '../entities/decision_entity.dart';

/// Contract between the Domain and Data layers for Decision operations.
abstract class DecisionRepository {
  /// Submits a SOC decision (APPROVE / REJECT / ESCALATE) for the given alert.
  Future<Either<Failure, DecisionEntity>> submitDecision({
    required String alertId,
    required String action,
    String? note,
  });

  /// Retrieves a cursor-paginated page of past decisions.
  Future<Either<Failure, PaginatedResponse<DecisionEntity>>> getDecisionHistory({
    String? cursor,
  });
}
