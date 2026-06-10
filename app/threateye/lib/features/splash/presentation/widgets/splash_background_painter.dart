import 'package:flutter/material.dart';

class SplashBackgroundPainter extends CustomPainter {
  const SplashBackgroundPainter();

  @override
  void paint(Canvas canvas, Size size) {

    final paint = Paint()
      ..color = const Color(0xFF1E2D45).withOpacity(0.5)
      ..strokeWidth = 0.5;

    const spacing = 32.0;

    for (double x = 0; x < size.width; x += spacing) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), paint);
    }

    for (double y = 0; y < size.height; y += spacing) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }
  }

  @override
  bool shouldRepaint(CustomPainter oldDelegate) => false;
}
