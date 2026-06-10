import '../../domain/entities/notification_entity.dart';
import '../../domain/repositories/notifications_repository.dart';
import '../datasources/notification_remote_data_source.dart';

/// Concrete [NotificationsRepository].
///
/// Sprint 3 — mock data purged. Delegates to [NotificationRemoteDataSource]
/// which calls `GET /v1/mobile/notifications` on the SecureNet backend.
class NotificationsRepositoryImpl implements NotificationsRepository {
  final NotificationRemoteDataSource _dataSource;

  const NotificationsRepositoryImpl(this._dataSource);

  @override
  Future<List<NotificationEntity>> getNotifications() async {
    // Returns the deserialized list from the API.
    // AppException subtypes propagate up to the cubit's catch block.
    return _dataSource.getNotifications();
  }
}
