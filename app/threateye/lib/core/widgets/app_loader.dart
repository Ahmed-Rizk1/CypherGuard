import 'package:flutter/material.dart';

import '../../config/theme/app_colors.dart';

/// Full-screen or inline loading indicator.
class AppLoader extends StatelessWidget {
  final bool fullScreen;
  final Color? color;

  const AppLoader({super.key, this.fullScreen = false, this.color});

  @override
  Widget build(BuildContext context) {
    final indicator = CircularProgressIndicator(
      strokeWidth: 2.5,
      valueColor: AlwaysStoppedAnimation<Color>(
        color ?? AppColors.primary,
      ),
    );

    if (fullScreen) {
      return Scaffold(
        backgroundColor: AppColors.backgroundPrimary,
        body: Center(child: indicator),
      );
    }

    return Center(child: indicator);
  }
}