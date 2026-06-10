import 'package:dartz/dartz.dart';
import 'package:threateye/core/error/exceptions.dart';
import 'package:threateye/core/error/failures.dart';
import '../../domain/entities/device_registration_entity.dart';
import '../../domain/repositories/notification_repository.dart';
import '../datasources/notification_remote_data_source.dart';
import '../models/device_registration_model.dart';

/// Concrete [NotificationRepository].
///
/// Maps [AppException] subtypes → [Failure] subtypes so the domain layer
/// stays free of HTTP/network concerns.
class NotificationRepositoryImpl implements NotificationRepository {
  final NotificationRemoteDataSource _dataSource;

  const NotificationRepositoryImpl(this._dataSource);

  @override
  Future<Either<Failure, void>> registerDevice(
    DeviceRegistrationEntity entity,
  ) async {
    try {
      final model = DeviceRegistrationModel.fromEntity(entity);
      await _dataSource.registerDevice(model);
      return const Right(null);
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
