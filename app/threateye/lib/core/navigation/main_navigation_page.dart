import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:threateye/config/router/route_names.dart';
import 'package:threateye/features/alerts/presentation/pages/alerts_page.dart';
import 'package:threateye/features/auth/presentation/pages/cubit/auth_cubit.dart';
import 'package:threateye/features/auth/presentation/pages/cubit/auth_state.dart';
import 'package:threateye/features/dashboard/presentation/pages/dashboard_page.dart';
import 'package:threateye/features/notifications/presentation/pages/notifications_page.dart';

class MainNavigationPage extends StatefulWidget {
  const MainNavigationPage({super.key});

  @override
  State<MainNavigationPage> createState() => _MainNavigationPageState();
}

class _MainNavigationPageState extends State<MainNavigationPage> {
  int _currentIndex = 0;

  static const List<_TabMeta> _tabs = [
    _TabMeta(
      label: 'Dashboard',
      icon: Icons.dashboard_outlined,
      activeIcon: Icons.dashboard,
    ),
    _TabMeta(
      label: 'Alerts',
      icon: Icons.warning_amber_outlined,
      activeIcon: Icons.warning_amber_rounded,
    ),
    _TabMeta(
      label: 'Notifications',
      icon: Icons.notifications_outlined,
      activeIcon: Icons.notifications,
    ),
  ];

  final List<Widget> _pages = const [
    DashboardPage(),
    AlertsPage(),
    NotificationsPage(),
  ];

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return BlocProvider(
      create: (_) => AuthCubit(),
      child: BlocListener<AuthCubit, AuthState>(
        listener: (context, state) {
          if (state is AuthUnauthenticated) {
            Navigator.pushNamedAndRemoveUntil(
              context, RouteNames.login, (route) => false,
            );
          }
        },
        child: Scaffold(
          appBar: AppBar(
            title: Row(
              children: [
                Icon(Icons.security, color: colorScheme.primary, size: 22),
                const SizedBox(width: 8),
                RichText(
                  text: TextSpan(
                    children: [
                      TextSpan(
                        text: 'Cypher',
                        style: theme.textTheme.titleLarge?.copyWith(
                          fontWeight: FontWeight.w800,
                          color: theme.appBarTheme.foregroundColor ??
                              colorScheme.onSurface,
                        ),
                      ),
                      TextSpan(
                        text: 'Guard',
                        style: theme.textTheme.titleLarge?.copyWith(
                          fontWeight: FontWeight.w800,
                          color: colorScheme.primary,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            actions: [
              // Builder is required here: the `context` from build() sits
              // ABOVE BlocProvider in the element tree, so context.read<AuthCubit>()
              // would fail. Builder provides `ctx` — a descendant context that
              // is BELOW BlocProvider — so ctx.read<AuthCubit>() resolves correctly.
              Builder(
                builder: (ctx) => IconButton(
                  icon: const Icon(Icons.logout_rounded),
                  tooltip: 'Logout',
                  onPressed: () => ctx.read<AuthCubit>().logout(),
                ),
              ),
            ],
          ),
          body: IndexedStack(
            index: _currentIndex,
            children: _pages,
          ),
          bottomNavigationBar: _buildBottomNavBar(colorScheme),
        ),
      ),
    );
  }

  Widget _buildBottomNavBar(ColorScheme colorScheme) {
    return Container(
      decoration: BoxDecoration(
        border: Border(
          top: BorderSide(
            color: colorScheme.outline.withOpacity(0.15),
            width: 1,
          ),
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.3),
            blurRadius: 12,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: (index) => setState(() => _currentIndex = index),
        type: BottomNavigationBarType.fixed,
        selectedItemColor: colorScheme.primary,
        unselectedItemColor:
            colorScheme.onSurface.withOpacity(0.45),
        selectedFontSize: 12,
        unselectedFontSize: 11,
        selectedLabelStyle: const TextStyle(fontWeight: FontWeight.w600),
        items: List.generate(
          _tabs.length,
          (i) => BottomNavigationBarItem(
            icon: Icon(_tabs[i].icon),
            activeIcon: Icon(_tabs[i].activeIcon),
            label: _tabs[i].label,
          ),
        ),
      ),
    );
  }
}

class _TabMeta {
  final String label;
  final IconData icon;
  final IconData activeIcon;

  const _TabMeta({
    required this.label,
    required this.icon,
    required this.activeIcon,
  });
}
