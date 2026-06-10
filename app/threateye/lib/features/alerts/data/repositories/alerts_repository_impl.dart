import 'package:dartz/dartz.dart';
import 'package:threateye/core/error/exceptions.dart';
import 'package:threateye/core/error/failures.dart';
import 'package:threateye/core/network/paginated_response.dart';
import '../../domain/entities/attack_alert_entity.dart';
import '../../domain/repositories/alerts_repository.dart';
import '../datasources/alerts_remote_data_source.dart';
import '../models/attack_alert_model.dart';

class AlertsRepositoryImpl implements AlertsRepository {
  final AlertsRemoteDataSource _dataSource;

  const AlertsRepositoryImpl(this._dataSource);

  // ── getAlerts ──────────────────────────────────────────────────────────────

  @override
  Future<Either<Failure, PaginatedResponse<AttackAlertEntity>>> getAlerts({
    String? severity,
    String? status,
    String? cursor,
  }) async {
    try {
      final page = await _dataSource.getAlerts(
        severity: severity,
        status:   status,
        cursor:   cursor,
      );
      // Up-cast: PaginatedResponse<AttackAlertModel> → <AttackAlertEntity>
      final entityPage = PaginatedResponse<AttackAlertEntity>(
        items:   page.items,
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

  // ── getAlertById ───────────────────────────────────────────────────────────

  @override
  Future<Either<Failure, AttackAlertEntity>> getAlertById(String id) async {
    try {
      final model = await _dataSource.getAlertById(id);
      return Right(model);
    } on NetworkException catch (e) {
      return Left(NetworkFailure(message: e.message));
    } on UnauthorizedException catch (e) {
      return Left(UnauthorizedFailure(message: e.message));
    } on NotFoundException {
      // 404 → surface as NotFoundFailure so Cubit can show specific UI
      return const Left(NotFoundFailure(
        message: 'This alert no longer exists.',
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

  // ── updateAlertStatus ──────────────────────────────────────────────────────

  @override
  Future<Either<Failure, AttackAlertEntity>> updateAlertStatus(
    String id,
    String status,
  ) async {
    try {
      final model = await _dataSource.updateAlertStatus(id, status);
      return Right(model);
    } on NetworkException catch (e) {
      return Left(NetworkFailure(message: e.message));
    } on UnauthorizedException catch (e) {
      return Left(UnauthorizedFailure(message: e.message));
    } on NotFoundException {
      return const Left(NotFoundFailure(
        message: 'Alert not found. It may have been deleted.',
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

  // ── private helper ─────────────────────────────────────────────────────────

  /// Converts an [AttackAlertModel] (from the data layer) into the domain
  /// [AttackAlertEntity] type without losing any fields.
  // ignore: unused_element
  AttackAlertEntity _toEntity(AttackAlertModel m) => m; // model IS-A entity
}

