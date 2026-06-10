import 'package:dartz/dartz.dart';
import 'package:threateye/core/error/failures.dart';
import 'package:threateye/core/usecases/usecase.dart';
import 'package:threateye/features/auth/domain/entities/auth_entity.dart';
import 'package:threateye/features/auth/domain/repositories/auth_repository.dart';

/// Exchanges the single-use refresh token for a fresh token pair.
/// Called exclusively by [AuthInterceptor] — never directly by the UI.
class RefreshTokenUseCase extends UseCase<AuthEntity, RefreshTokenParams> {
  final AuthRepository _repository;

  RefreshTokenUseCase(this._repository);

  @override
  Future<Either<Failure, AuthEntity>> call(RefreshTokenParams params) =>
      _repository.refreshToken(params.refreshToken);
}

class RefreshTokenParams {
  final String refreshToken;
  const RefreshTokenParams({required this.refreshToken});
}
