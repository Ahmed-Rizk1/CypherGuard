import 'package:dartz/dartz.dart';
import 'package:threateye/core/error/failures.dart';
import 'package:threateye/core/usecases/usecase.dart';
import 'package:threateye/features/auth/domain/repositories/auth_repository.dart';

class LogoutUseCase extends UseCase<void, NoParams> {
  final AuthRepository _repository;

  LogoutUseCase(this._repository);

  @override
  Future<Either<Failure, void>> call(NoParams params) =>
      _repository.logout();
}
