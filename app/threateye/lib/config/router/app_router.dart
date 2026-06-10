import 'package:flutter/material.dart';
import 'package:threateye/core/navigation/main_navigation_page.dart';
import 'package:threateye/features/alerts/presentation/pages/alert_detail_page.dart';
import 'package:threateye/features/alerts/presentation/pages/alerts_page.dart';
import 'package:threateye/features/dashboard/presentation/pages/dashboard_page.dart';
import 'package:threateye/features/decision/presentation/pages/decision_history_page.dart';
import 'package:threateye/features/firewall/presentation/pages/firewall_page.dart';
import 'package:threateye/features/notifications/presentation/pages/notifications_page.dart';
import '../../features/auth/presentation/pages/login_page.dart';
import '../../features/splash/presentation/pages/splash_page.dart';

import 'route_names.dart';

class AppRouter {
  static Route<dynamic>? onGenerateRoute(RouteSettings settings) {
    switch (settings.name) {
      case RouteNames.splash:
        return MaterialPageRoute(builder: (_) => const SplashPage());

      case RouteNames.login:
        return MaterialPageRoute(builder: (_) => const LoginPage());

      case RouteNames.main:
        return MaterialPageRoute(builder: (_) => const MainNavigationPage());

      case RouteNames.dashboard:
        return MaterialPageRoute(builder: (_) => const DashboardPage());

      case RouteNames.alerts:
        return MaterialPageRoute(builder: (_) => const AlertsPage());

      case RouteNames.alertDetail:
        return MaterialPageRoute(
          settings: settings,
          builder: (_) => const AlertDetailPage(),
        );

      case RouteNames.notifications:
        return MaterialPageRoute(builder: (_) => const NotificationsPage());

      // ── Sprint 2: hidden routes ──────────────────────────────────────────
      case RouteNames.firewall:
        return MaterialPageRoute(builder: (_) => const FirewallPage());

      case RouteNames.decisionHistory:
        return MaterialPageRoute(builder: (_) => const DecisionHistoryPage());
      default:
        return null;
    }
  }
}
