import 'package:flutter/material.dart';

class SkeletonLoadingList extends StatefulWidget {
  const SkeletonLoadingList({super.key});

  @override
  State<SkeletonLoadingList> createState() => _SkeletonLoadingListState();
}

class _SkeletonLoadingListState extends State<SkeletonLoadingList>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _animation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1100),
    )..repeat(reverse: true);
    _animation = Tween<double>(
      begin: 0.25,
      end: 0.85,
    ).animate(CurvedAnimation(parent: _controller, curve: Curves.easeInOut));
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _animation,
      builder: (context, _) {
        return ListView.builder(
          padding: const EdgeInsets.fromLTRB(14, 14, 14, 8),
          itemCount: 7,
          itemBuilder: (_, __) => SkeletonCard(opacity: _animation.value),
        );
      },
    );
  }
}

class SkeletonCard extends StatelessWidget {
  final double opacity;
  const SkeletonCard({super.key, required this.opacity});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final base = isDark ? Colors.white : Colors.black;

    Widget bone(double w, double h, {double radius = 6}) => Container(
      width: w,
      height: h,
      decoration: BoxDecoration(
        color: base.withValues(alpha: opacity * 0.13),
        borderRadius: BorderRadius.circular(radius),
      ),
    );

    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
        child: Row(
          children: [
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: base.withValues(alpha: opacity * 0.10),
                borderRadius: BorderRadius.circular(12),
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  bone(double.infinity, 13),
                  const SizedBox(height: 9),
                  bone(170, 11),
                ],
              ),
            ),
            const SizedBox(width: 14),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                bone(54, 22, radius: 20),
                const SizedBox(height: 6),
                bone(38, 10),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
