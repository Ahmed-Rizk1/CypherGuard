import 'dart:ui';

import 'package:flutter_local_notifications/flutter_local_notifications.dart';

import 'logger_service.dart';
class LocalNotificationService {
  LocalNotificationService._();

  static final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();

  static const AndroidNotificationChannel _androidChannel =
      AndroidNotificationChannel(
    'cypherguard_alerts',
    'CypherGuard Alerts',
    description: 'Cyber attack alert notifications',
    importance: Importance.high,
    playSound: true,
  );

  static Future<void> init() async {
    const androidSettings =
        AndroidInitializationSettings('@mipmap/ic_launcher');

    const iosSettings = DarwinInitializationSettings(
      requestAlertPermission: true,
      requestBadgePermission: true,
      requestSoundPermission: true,
    );

    const initSettings = InitializationSettings(
      android: androidSettings,
      iOS: iosSettings,
    );

    await _plugin.initialize(initSettings);

    await _plugin
        .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>()
        ?.createNotificationChannel(_androidChannel);

    LoggerService.info('[LocalNotificationService] Initialized.');
  }

  static Future<void> showAlertNotification({
    required int id,
    required String title,
    required String body,
  }) async {
    const androidDetails = AndroidNotificationDetails(
      'cypherguard_alerts',
      'CypherGuard Alerts',
      channelDescription: 'Cyber attack alert notifications',
      importance: Importance.high,
      priority: Priority.high,
      color: Color(0xFF2563EB),
    );

    const iosDetails = DarwinNotificationDetails(
      presentAlert: true,
      presentBadge: true,
      presentSound: true,
    );

    await _plugin.show(
      id,
      title,
      body,
      const NotificationDetails(
        android: androidDetails,
        iOS: iosDetails,
      ),
    );
  }

  static Future<void> cancelAll() async {
    await _plugin.cancelAll();
  }
}
