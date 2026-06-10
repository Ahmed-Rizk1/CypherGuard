import 'package:dartz/dartz.dart';
import 'package:equatable/equatable.dart';
import 'package:threateye/core/error/failures.dart';
import 'package:threateye/core/usecases/usecase.dart';
import 'package:threateye/features/auth/domain/entities/auth_entity.dart';
import 'package:threateye/features/auth/domain/repositories/auth_repository.dart';

class LoginUseCase extends UseCase<AuthEntity, LoginParams> {
  final AuthRepository _repository;

  LoginUseCase(this._repository);

  @override
  Future<Either<Failure, AuthEntity>> call(LoginParams params) =>
      _repository.login(params.email, params.password);
}

class LoginParams extends Equatable {
  final String email;
  final String password;

  const LoginParams({required this.email, required this.password});

  @override
  List<Object?> get props => [email, password];
}
