import 'package:flutter/material.dart';
import 'package:threateye/config/constants/api_constants.dart';
import 'package:threateye/core/services/secure_storage_service.dart';
import 'package:threateye/features/splash/presentation/widgets/splash_background_painter.dart';
import 'package:threateye/injection_container.dart';
import '../../../../config/constants/app_constants.dart';
import '../../../../config/router/route_names.dart';
import '../../../../config/theme/app_colors.dart';

import '../widgets/splash_logo.dart';
import '../widgets/splash_app_name.dart';
import '../widgets/splash_tagline.dart';
import '../widgets/splash_loader.dart';
import '../widgets/splash_version.dart';


class SplashPage extends StatefulWidget {
  const SplashPage({super.key});

  @override
  State<SplashPage> createState() => _SplashPageState();
}

class _SplashPageState extends State<SplashPage>
    with SingleTickerProviderStateMixin {

  late AnimationController controller;
  late Animation<double> fade;
  late Animation<double> scale;
  late Animation<double> pulse;

  @override
  void initState() {
    super.initState();
    _setupAnimations();
    _navigate();
  }

  void _setupAnimations() {
    controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    );

    fade = Tween(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: controller, curve: const Interval(0, 0.6)),
    );

    scale = Tween(begin: 0.75, end: 1.0).animate(
      CurvedAnimation(parent: controller, curve: const Interval(0, 0.6)),
    );

    pulse = Tween(begin: 1.0, end: 1.06).animate(
      CurvedAnimation(parent: controller, curve: const Interval(0.6, 1)),
    );

    controller.forward();

    controller.addStatusListener((status) {
      if (status == AnimationStatus.completed) {
        controller.reverse();
      } else if (status == AnimationStatus.dismissed) {
        controller.forward();
      }
    });
  }

  Future<void> _navigate() async {
    await Future.delayed(
      const Duration(milliseconds: AppConstants.splashDurationMs),
    );
    if (!mounted) return;

    final storage = sl<SecureStorageService>();
    final token = await storage.read(ApiConstants.accessTokenKey);

    if (!mounted) return;

    if (token != null && token.isNotEmpty) {
      Navigator.pushReplacementNamed(context, RouteNames.main);
    } else {
      Navigator.pushReplacementNamed(context, RouteNames.login);
    }
  }

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.backgroundPrimary,
      body: Stack(
        children: [
          const Positioned.fill(
            child: CustomPaint(
              painter: SplashBackgroundPainter(),
            ),
          ),
          Center(
            child: AnimatedBuilder(
              animation: controller,
              builder: (_, child) {
                return FadeTransition(
                  opacity: fade,
                  child: Transform.scale(
                    scale: scale.value * pulse.value,
                    child: child,
                  ),
                );
              },
              child: const Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  SplashLogo(),
                  SizedBox(height: 32),
                  SplashAppName(),
                  SizedBox(height: 8),
                  SplashTagline(),
                  SizedBox(height: 48),
                  SplashLoader(),
                ],
              ),
            ),
          ),
          const SplashVersion(),
        ],
      ),
    );
  }
}
