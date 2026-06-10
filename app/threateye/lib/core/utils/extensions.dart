import 'package:flutter/material.dart';

import '../../config/theme/app_colors.dart';
import 'app_enums.dart';

extension StringExtensions on String {
  String get capitalize =>
      isEmpty ? this : '${this[0].toUpperCase()}${substring(1)}';

  bool get isValidEmail =>
      RegExp(r'^[\w-\.]+@([\w-]+\.)+[\w-]{2,4}$').hasMatch(this);

  bool get isValidIp =>
      RegExp(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$').hasMatch(this);
}

extension AlertSeverityExtensions on AlertSeverity {
  String get label {
    switch (this) {
      case AlertSeverity.critical: return 'Critical';
      case AlertSeverity.high:     return 'High';
      case AlertSeverity.medium:   return 'Medium';
      case AlertSeverity.low:      return 'Low';
    }
  }

  Color get color {
    switch (this) {
      case AlertSeverity.critical: return AppColors.severityCritical;
      case AlertSeverity.high:     return AppColors.severityHigh;
      case AlertSeverity.medium:   return AppColors.severityMedium;
      case AlertSeverity.low:      return AppColors.severityLow;
    }
  }

  Color get backgroundColor {
    switch (this) {
      case AlertSeverity.critical: return AppColors.severityCriticalBg;
      case AlertSeverity.high:     return AppColors.severityHighBg;
      case AlertSeverity.medium:   return AppColors.severityMediumBg;
      case AlertSeverity.low:      return AppColors.severityLowBg;
    }
  }
}

extension AttackTypeExtensions on AttackType {
  String get label {
    switch (this) {
      case AttackType.ddos:              return 'DDoS';
      case AttackType.sqlInjection:      return 'SQL Injection';
      case AttackType.bruteForce:        return 'Brute Force';
      case AttackType.xss:               return 'XSS';
      case AttackType.malware:           return 'Malware';
      case AttackType.suspiciousNetwork: return 'Suspicious Network';
      case AttackType.unknown:           return 'Unknown';
    }
  }

  IconData get icon {
    switch (this) {
      case AttackType.ddos:              return Icons.cloud_off_rounded;
      case AttackType.sqlInjection:      return Icons.storage_rounded;
      case AttackType.bruteForce:        return Icons.lock_open_rounded;
      case AttackType.xss:               return Icons.code_rounded;
      case AttackType.malware:           return Icons.bug_report_rounded;
      case AttackType.suspiciousNetwork: return Icons.wifi_tethering_error_rounded;
      case AttackType.unknown:           return Icons.help_outline_rounded;
    }
  }
}

extension ContextExtensions on BuildContext {
  ThemeData get theme => Theme.of(this);
  TextTheme get textTheme => Theme.of(this).textTheme;
  ColorScheme get colorScheme => Theme.of(this).colorScheme;
  Size get screenSize => MediaQuery.of(this).size;
  double get screenWidth => MediaQuery.of(this).size.width;
  double get screenHeight => MediaQuery.of(this).size.height;
}