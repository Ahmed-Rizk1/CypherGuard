import 'package:flutter/material.dart';
import '../../../../config/constants/app_constants.dart';

class SplashVersion extends StatelessWidget {
  const SplashVersion({super.key});

  @override
  Widget build(BuildContext context) {
    return const Positioned(
      bottom: 24,
      left: 0,
      right: 0,
      child: Text(
        "v${AppConstants.appVersion}",
        textAlign: TextAlign.center,
      ),
    );
  }
}
