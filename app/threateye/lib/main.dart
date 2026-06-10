import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'package:threateye/config/router/route_names.dart';
import 'package:threateye/config/theme/app_theme.dart';
import 'package:threateye/core/services/navigation_service.dart';
import 'config/router/app_router.dart';
import 'injection_container.dart' as di;

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.light,
      systemNavigationBarColor: Color(0xFF0A0E1A),
      systemNavigationBarIconBrightness: Brightness.light,
    ),
  );
  await di.init();
  runApp(const CypherGuardApp());
}

class CypherGuardApp extends StatelessWidget {
  const CypherGuardApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'CypherGuard',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme,
      navigatorKey: NavigationService.navigatorKey,
      onGenerateRoute: AppRouter.onGenerateRoute,
      initialRoute: RouteNames.splash,
    );
  }
}
