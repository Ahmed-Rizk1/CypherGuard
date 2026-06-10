import 'package:dartz/dartz.dart';
import 'package:threateye/core/error/exceptions.dart';
import 'package:threateye/core/error/failures.dart';
import 'package:threateye/core/network/paginated_response.dart';
import '../../domain/entities/decision_entity.dart';
import '../../domain/repositories/decision_repository.dart';
import '../datasources/decision_remote_data_source.dart';

class DecisionRepositoryImpl implements DecisionRepository {
  final DecisionRemoteDataSource _dataSource;

  const DecisionRepositoryImpl(this._dataSource);

  // ── submitDecision ─────────────────────────────────────────────────────────

  @override
  Future<Either<Failure, DecisionEntity>> submitDecision({
    required String alertId,
    required String action,
    String? note,
  }) async {
    try {
      final model = await _dataSource.submitDecision(
        alertId: alertId,
        action:  action,
        note:    note,
      );
      return Right(model);
    } on NetworkException catch (e) {
      return Left(NetworkFailure(message: e.message));
    } on UnauthorizedException catch (e) {
      return Left(UnauthorizedFailure(message: e.message));
    } on NotFoundException {
      return const Left(NotFoundFailure(
        message: 'The referenced alert was not found.',
      ));
    } on ServerException catch (e) {
      return Left(ServerFailure(
        message:    e.message,
        statusCode: e.statusCode,
        errorCode:  e.errorCode,
      ));
    } catch (e) {
      return Left(UnexpectedFailure(message: e.toString()));
    }
  }

  // ── getDecisionHistory ─────────────────────────────────────────────────────

  @override
  Future<Either<Failure, PaginatedResponse<DecisionEntity>>> getDecisionHistory({
    String? cursor,
  }) async {
    try {
      final page = await _dataSource.getDecisionHistory(cursor: cursor);
      final entityPage = PaginatedResponse<DecisionEntity>(
        items:   page.items,   // DecisionModel IS-A DecisionEntity
        cursor:  page.cursor,
        hasNext: page.hasNext,
      );
      return Right(entityPage);
    } on NetworkException catch (e) {
      return Left(NetworkFailure(message: e.message));
    } on UnauthorizedException catch (e) {
      return Left(UnauthorizedFailure(message: e.message));
    } on ServerException catch (e) {
      return Left(ServerFailure(
        message:    e.message,
        statusCode: e.statusCode,
        errorCode:  e.errorCode,
      ));
    } catch (e) {
      return Left(UnexpectedFailure(message: e.toString()));
    }
  }
}
