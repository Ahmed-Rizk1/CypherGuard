import 'package:flutter/material.dart';
import '../../../../config/theme/app_text_styles.dart';
import '../../../../config/theme/app_colors.dart';

class SplashTagline extends StatelessWidget {
  const SplashTagline({super.key});

  @override
  Widget build(BuildContext context) {
    return Text(
      'Cyber Attack Detection & Response',
      style: AppTextStyles.bodySmall.copyWith(
        color: AppColors.textMuted,
      ),
    );
  }
}
