import 'package:flutter/material.dart';

/// Provides a [GlobalKey<NavigatorState>] that works outside the widget tree.
///
/// Wire it into [MaterialApp.navigatorKey] once in [main.dart], then call
/// [pushReplacementNamed] from anywhere — including network interceptors —
/// without needing a [BuildContext].
class NavigationService {
  NavigationService._();

  static final GlobalKey<NavigatorState> navigatorKey =
      GlobalKey<NavigatorState>(debugLabel: 'rootNavigator');

  /// Clears the entire navigation stack and pushes [routeName].
  /// Safe to call from interceptors, services, or background isolates.
  static void pushReplacementNamed(String routeName) {
    navigatorKey.currentState?.pushNamedAndRemoveUntil(
      routeName,
      (_) => false,
    );
  }
}
