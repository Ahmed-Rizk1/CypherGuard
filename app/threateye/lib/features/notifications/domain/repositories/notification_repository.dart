import 'package:dartz/dartz.dart';
import 'package:threateye/core/error/failures.dart';
import '../entities/device_registration_entity.dart';

/// Abstract contract for device-registration operations.
abstract class NotificationRepository {
  /// Registers the device FCM token with the backend.
  ///
  /// Returns [Right(null)] on success, or a [Failure] on any error.
  Future<Either<Failure, void>> registerDevice(
    DeviceRegistrationEntity entity,
  );
}
