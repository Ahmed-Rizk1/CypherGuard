import 'package:dartz/dartz.dart';
import 'package:threateye/core/error/exceptions.dart';
import 'package:threateye/core/error/failures.dart';
import 'package:threateye/core/network/paginated_response.dart';
import '../../domain/entities/blocked_ip_entity.dart';
import '../../domain/repositories/firewall_repository.dart';
import '../datasources/firewall_remote_data_source.dart';

class FirewallRepositoryImpl implements FirewallRepository {
  final FirewallRemoteDataSource _dataSource;

  const FirewallRepositoryImpl(this._dataSource);

  // ── getBlockedIps ──────────────────────────────────────────────────────────

  @override
  Future<Either<Failure, PaginatedResponse<BlockedIpEntity>>> getBlockedIps({
    String? cursor,
  }) async {
    try {
      final page = await _dataSource.getBlockedIps(cursor: cursor);
      final entityPage = PaginatedResponse<BlockedIpEntity>(
        items:   page.items,   // BlockedIpModel IS-A BlockedIpEntity
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

  // ── blockIp ────────────────────────────────────────────────────────────────

  @override
  Future<Either<Failure, BlockedIpEntity>> blockIp({
    required String ipAddress,
    required String reason,
  }) async {
    try {
      final model = await _dataSource.blockIp(
        ipAddress: ipAddress,
        reason:    reason,
      );
      return Right(model);
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

  // ── unblockIp ──────────────────────────────────────────────────────────────

  @override
  Future<Either<Failure, void>> unblockIp(String ipAddress) async {
    try {
      await _dataSource.unblockIp(ipAddress);
      return const Right(null);
    } on NetworkException catch (e) {
      return Left(NetworkFailure(message: e.message));
    } on UnauthorizedException catch (e) {
      return Left(UnauthorizedFailure(message: e.message));
    } on NotFoundException {
      return const Left(NotFoundFailure(
        message: 'This IP block no longer exists.',
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
}
