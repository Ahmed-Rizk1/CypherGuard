import 'package:dartz/dartz.dart';
import 'package:threateye/core/error/exceptions.dart';
import 'package:threateye/core/error/failures.dart';
import 'package:threateye/features/auth/data/datasources/auth_remote_data_source.dart';
import 'package:threateye/features/auth/data/models/auth_response_model.dart';
import 'package:threateye/features/auth/domain/entities/auth_entity.dart';
import 'package:threateye/features/auth/domain/repositories/auth_repository.dart';

/// Concrete implementation of [AuthRepository].
/// Converts [AuthResponseModel] ↔ [AuthEntity] and maps [AppException]s to
/// [Failure] subtypes so the domain layer stays free of network concerns.
class AuthRepositoryImpl implements AuthRepository {
  final AuthRemoteDataSource _dataSource;

  AuthRepositoryImpl(this._dataSource);

  // ── login ──────────────────────────────────────────────────────────────────

  @override
  Future<Either<Failure, AuthEntity>> login(
    String email,
    String password,
  ) async {
    try {
      final model = await _dataSource.login(email, password);
      return Right(_toEntity(model));
    } on UnauthorizedException catch (e) {
      return Left(UnauthorizedFailure(message: e.message));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(message: e.message));
    } on ServerException catch (e) {
      return Left(
        ServerFailure(
          message: e.message,
          statusCode: e.statusCode,
          errorCode: e.errorCode,
        ),
      );
    } catch (e) {
      return Left(UnexpectedFailure(message: e.toString()));
    }
  }

  @override
  Future<Either<Failure, AuthEntity>> refreshToken(String refreshToken) async {
    try {
      final model = await _dataSource.refreshToken(refreshToken);
      return Right(_toEntity(model));
    } on UnauthorizedException catch (e) {
      return Left(UnauthorizedFailure(message: e.message));
    } on NetworkException catch (e) {
      return Left(NetworkFailure(message: e.message));
    } on ServerException catch (e) {
      return Left(
        ServerFailure(
          message: e.message,
          statusCode: e.statusCode,
          errorCode: e.errorCode,
        ),
      );
    } catch (e) {
      return Left(UnexpectedFailure(message: e.toString()));
    }
  }

  // ── logout ─────────────────────────────────────────────────────────────────

  @override
  Future<Either<Failure, void>> logout() async {
    try {
      await _dataSource.logout();
      return const Right(null);
    } catch (e) {
      return Left(UnexpectedFailure(message: e.toString()));
    }
  }

  AuthEntity _toEntity(AuthResponseModel m) => AuthEntity(
    accessToken: m.accessToken,
    refreshToken: m.refreshToken,
    tokenType: m.tokenType,
    expiresIn: m.expiresIn,
    role: m.role,
  );
}
