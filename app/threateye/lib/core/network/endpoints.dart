class Endpoints {
  Endpoints._();

  static const String login = '/v1/mobile/auth';
  static const String refreshToken = '/v1/mobile/auth/refresh';
  static const String logout = '/v1/mobile/auth/logout';

  static const String dashboardSummary = '/v1/mobile/dashboard/summary';
  static const String alerts = '/v1/mobile/alerts';

  static String alertById(String id) => '/v1/mobile/alerts/$id';

  static const String firewall = '/v1/mobile/firewall';
  static const String firewallBlock = '/v1/mobile/firewall/block';
  static String firewallUnblock(String ip) => '/v1/mobile/firewall/block/$ip';
  static const String submitDecision = '/v1/mobile/decision';
  static const String decisions = '/v1/mobile/decisions';
  // Reserved for future analytics module (currently unused)
  // static const String reports = '/v1/mobile/reports';
  // static const String reportSummary = '/v1/mobile/reports/summary';

  static const String notifications = '/v1/mobile/notifications';
  static String markNotificationRead(String id) => '/v1/mobile/notifications/$id/read';
  static const String markAllNotificationsRead = '/v1/mobile/notifications/read-all';
}
