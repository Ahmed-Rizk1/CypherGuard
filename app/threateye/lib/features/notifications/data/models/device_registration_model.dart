import '../../domain/entities/device_registration_entity.dart';

/// Data-transfer model for `POST /v1/mobile/devices/register`.
///
/// Converts the domain [DeviceRegistrationEntity] into the exact JSON body
/// the backend expects.
class DeviceRegistrationModel {
  final String fcmToken;
  final String deviceName;
  final String platform;

  const DeviceRegistrationModel({
    required this.fcmToken,
    required this.deviceName,
    required this.platform,
  });

  /// Creates a model from a domain entity.
  factory DeviceRegistrationModel.fromEntity(DeviceRegistrationEntity entity) {
    return DeviceRegistrationModel(
      fcmToken:   entity.fcmToken,
      deviceName: entity.deviceName,
      platform:   entity.platform,
    );
  }

  /// Serialises to the JSON body required by the backend.
  Map<String, dynamic> toJson() => {
        'fcm_token':   fcmToken,
        'device_name': deviceName,
        'platform':    platform,
      };
}
