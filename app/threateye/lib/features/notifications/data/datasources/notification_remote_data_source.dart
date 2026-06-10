import 'package:threateye/core/network/api_client.dart';
import '../models/device_registration_model.dart';
import '../models/notification_model.dart';

/// Contract for notification-related remote operations.
abstract class NotificationRemoteDataSource {
  /// Registers the device with the backend.
  ///
  /// Throws an [AppException] subtype on any network / server error.
  Future<void> registerDevice(DeviceRegistrationModel model);

  /// Fetches the latest notifications from `GET /v1/mobile/notifications`.
  ///
  /// Returns a list of [NotificationModel]. Throws an [AppException]
  /// subtype on any network / server error.
  Future<List<NotificationModel>> getNotifications();
}

/// Concrete implementation backed by the SecureNet REST API.
class NotificationRemoteDataSourceImpl implements NotificationRemoteDataSource {
  final ApiClient _apiClient;

  const NotificationRemoteDataSourceImpl(this._apiClient);

  @override
  Future<void> registerDevice(DeviceRegistrationModel model) async {
    // ApiClient.post already throws AppException subtypes on error,
    // so no manual status-code handling is needed here.
    await _apiClient.post(
      '/v1/mobile/devices/register',
      data: model.toJson(),
    );
  }

  @override
  Future<List<NotificationModel>> getNotifications() async {
    final response = await _apiClient.get('/v1/mobile/notifications');

    // response is a Dio Response — the actual payload is in response.data.
    // The backend returns either a bare list or a wrapped envelope.
    // Handle both shapes defensively.
    final dynamic body = response.data;
    final List<dynamic> raw = body is List
        ? body
        : ((body as Map<String, dynamic>)['data']
              ?? body['results']
              ?? body['notifications']
              ?? <dynamic>[]) as List<dynamic>;

    return raw
        .map((e) => NotificationModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }
}
