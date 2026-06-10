import '../../domain/entities/notification_entity.dart';

class NotificationModel extends NotificationEntity {
  NotificationModel({
    required super.id,
    required super.title,
    required super.message,
    required super.time,
    required super.type,
  });

  /// Deserialises a JSON map from the backend into a [NotificationModel].
  ///
  /// Field names are mapped defensively to cover common API conventions
  /// (`created_at` vs `time`, `body` vs `message`, etc.).
  factory NotificationModel.fromJson(Map<String, dynamic> json) {
    return NotificationModel(
      id:      (json['id']      ?? json['_id']   ?? '').toString(),
      title:   (json['title']   ?? json['subject'] ?? 'Security Alert').toString(),
      message: (json['message'] ?? json['body']    ?? json['description'] ?? '').toString(),
      time:    (json['time']    ?? json['created_at'] ?? json['timestamp'] ?? '').toString(),
      type:    (json['type']    ?? json['category']   ?? 'System').toString(),
    );
  }
}
