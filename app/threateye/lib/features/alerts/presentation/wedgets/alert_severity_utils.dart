import 'package:flutter/material.dart';

class AlertSeverityUtils {
  // ─── Severity colour ─────────────────────────────────────────────
  static Color severityColor(String severity) {
    switch (severity.toLowerCase()) {
      case 'critical':
        return const Color(0xFFEF4444);
      case 'high':
        return const Color(0xFFF97316);
      case 'medium':
        return const Color(0xFFF59E0B);
      default:
        return const Color(0xFF22C55E);
    }
  }

  // ─── Status colour ───────────────────────────────────────────────
  static Color statusColor(String status) {
    switch (status.toLowerCase()) {
      case 'active':
        return const Color(0xFFEF4444);
      case 'investigating':
        return const Color(0xFFF97316);
      case 'resolved':
        return const Color(0xFF22C55E);
      default:
        return Colors.blueGrey;
    }
  }

  // ─── Severity icon ───────────────────────────────────────────────
  static IconData severityIcon(String severity) {
    switch (severity.toLowerCase()) {
      case 'critical':
        return Icons.local_fire_department_rounded;
      case 'high':
        return Icons.warning_amber_rounded;
      case 'medium':
        return Icons.info_outline_rounded;
      default:
        return Icons.check_circle_outline_rounded;
    }
  }

  // ─── Response actions ────────────────────────────────────────────
  static List<Map<String, dynamic>> responseActions(String attackType) {
    final type = attackType.toLowerCase();
    if (type.contains('brute force') || type.contains('bruteforce')) {
      return [
        {'icon': Icons.block_rounded, 'label': 'Block source IP'},
        {'icon': Icons.vpn_key_rounded, 'label': 'Reset affected credentials'},
        {'icon': Icons.verified_user_rounded, 'label': 'Enable MFA'},
        {'icon': Icons.manage_search_rounded, 'label': 'Monitor authentication logs'},
      ];
    } else if (type.contains('malware') || type.contains('ransomware')) {
      return [
        {'icon': Icons.device_unknown_rounded, 'label': 'Isolate infected device'},
        {'icon': Icons.bug_report_rounded, 'label': 'Run antivirus scan'},
        {'icon': Icons.wifi_off_rounded, 'label': 'Disconnect from network'},
        {'icon': Icons.list_alt_rounded, 'label': 'Review suspicious processes'},
      ];
    } else if (type.contains('ddos') || type.contains('dos')) {
      return [
        {'icon': Icons.speed_rounded, 'label': 'Enable rate limiting'},
        {'icon': Icons.traffic_rounded, 'label': 'Block malicious traffic'},
        {'icon': Icons.shield_rounded, 'label': 'Activate firewall protection'},
        {'icon': Icons.bar_chart_rounded, 'label': 'Monitor bandwidth usage'},
      ];
    } else if (type.contains('phishing') || type.contains('social engineering')) {
      return [
        {'icon': Icons.campaign_rounded, 'label': 'Warn affected users'},
        {'icon': Icons.lock_reset_rounded, 'label': 'Reset compromised passwords'},
        {'icon': Icons.attach_email_rounded, 'label': 'Scan email attachments'},
        {'icon': Icons.email_rounded, 'label': 'Review email gateway logs'},
      ];
    } else {
      return [
        {'icon': Icons.find_in_page_rounded, 'label': 'Investigate logs'},
        {'icon': Icons.monitor_heart_rounded, 'label': 'Monitor network activity'},
        {'icon': Icons.escalator_warning_rounded, 'label': 'Escalate to SOC analyst'},
      ];
    }
  }
}
