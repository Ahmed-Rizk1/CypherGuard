/// Domain entity representing the data needed to register a device for FCM.
class DeviceRegistrationEntity {
  final String fcmToken;
  final String deviceName;
  final String platform;

  const DeviceRegistrationEntity({
    required this.fcmToken,
    required this.deviceName,
    required this.platform,
  });
}
