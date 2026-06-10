import 'package:flutter/material.dart';

/// ThreatPulse design system color palette.
/// All colors across the app must reference this class.
class AppColors {
  AppColors._();

  // ── Background ─────────────────────────────────────
  static const Color backgroundPrimary = Color(0xFF0A0E1A);
  static const Color backgroundSecondary = Color(0xFF111827);
  static const Color backgroundCard = Color(0xFF161D2F);
  static const Color backgroundElevated = Color(0xFF1C2539);

  // ── Brand / Primary ────────────────────────────────
  static const Color primary = Color(0xFF2563EB);
  static const Color primaryLight = Color(0xFF3B82F6);
  static const Color primaryDark = Color(0xFF1D4ED8);
  static const Color primaryGlow = Color(0x332563EB);

  // ── Accent ─────────────────────────────────────────
  static const Color accent = Color(0xFF06B6D4);
  static const Color accentGlow = Color(0x2206B6D4);

  // ── Severity ───────────────────────────────────────
  static const Color severityCritical = Color(0xFFE53E3E);
  static const Color severityCriticalBg = Color(0x1AE53E3E);
  static const Color severityHigh = Color(0xFFED8936);
  static const Color severityHighBg = Color(0x1AED8936);
  static const Color severityMedium = Color(0xFFECC94B);
  static const Color severityMediumBg = Color(0x1AECC94B);
  static const Color severityLow = Color(0xFF48BB78);
  static const Color severityLowBg = Color(0x1A48BB78);

  // ── Status ─────────────────────────────────────────
  static const Color statusSuccess = Color(0xFF48BB78);
  static const Color statusSuccessBg = Color(0x1A48BB78);
  static const Color statusWarning = Color(0xFFECC94B);
  static const Color statusWarningBg = Color(0x1AECC94B);
  static const Color statusError = Color(0xFFE53E3E);
  static const Color statusErrorBg = Color(0x1AE53E3E);
  static const Color statusInfo = Color(0xFF2563EB);
  static const Color statusInfoBg = Color(0x1A2563EB);

  // ── Text ───────────────────────────────────────────
  static const Color textPrimary = Color(0xFFE2E8F0);
  static const Color textSecondary = Color(0xFF8892A4);
  static const Color textMuted = Color(0xFF4A5568);
  static const Color textOnPrimary = Color(0xFFFFFFFF);

  // ── Border ─────────────────────────────────────────
  static const Color borderDefault = Color(0xFF1E2D45);
  static const Color borderFocus = Color(0xFF2563EB);
  static const Color borderError = Color(0xFFE53E3E);

  // ── Divider ────────────────────────────────────────
  static const Color divider = Color(0xFF1A2235);

  // ── Overlay ────────────────────────────────────────
  static const Color overlay = Color(0x80000000);

  // ── Gradient stops ─────────────────────────────────
  static const List<Color> primaryGradient = [
    Color(0xFF1D4ED8),
    Color(0xFF2563EB),
    Color(0xFF06B6D4),
  ];

  static const List<Color> splashGradient = [
    Color(0xFF0A0E1A),
    Color(0xFF0F172A),
    Color(0xFF0A0E1A),
  ];
}