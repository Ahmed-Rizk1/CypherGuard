import 'package:flutter/material.dart';

import '../../config/theme/app_colors.dart';

/// General-purpose utility helpers used across features.
class Helpers {
  Helpers._();

  /// Shows a styled snackbar.
  static void showSnackBar(
    BuildContext context,
    String message, {
    bool isError = false,
    bool isSuccess = false,
  }) {
    final color = isError
        ? AppColors.statusError
        : isSuccess
            ? AppColors.statusSuccess
            : AppColors.primary;

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: color,
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 3),
      ),
    );
  }

  /// Returns initials from a full name.
  static String getInitials(String name) {
    final parts = name.trim().split(' ');
    if (parts.isEmpty) return '';
    if (parts.length == 1) return parts[0][0].toUpperCase();
    return '${parts[0][0]}${parts[1][0]}'.toUpperCase();
  }
}