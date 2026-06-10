import 'package:dartz/dartz.dart';
import 'package:threateye/core/error/failures.dart';
import '../entities/device_registration_entity.dart';
import '../repositories/notification_repository.dart';

/// Registers the current device for FCM push notifications.
///
/// This is called once, silently, after a successful login.
class RegisterDeviceUseCase {
  final NotificationRepository _repository;

  const RegisterDeviceUseCase(this._repository);

  Future<Either<Failure, void>> call(DeviceRegistrationEntity params) {
    return _repository.registerDevice(params);
  }
}
