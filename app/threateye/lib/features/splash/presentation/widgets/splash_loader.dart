import 'package:flutter/material.dart';


class SplashLoader extends StatelessWidget {
  const SplashLoader({super.key});

  @override
  Widget build(BuildContext context) {
    return const Column(
      children: [
        SizedBox(
          width: 140,
          child: LinearProgressIndicator(),
        ),
        SizedBox(height: 12),
        Text("Initializing security layer..."),
      ],
    );
  }
}
