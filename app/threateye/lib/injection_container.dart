import 'package:dio/dio.dart';
import 'package:get_it/get_it.dart';
import 'package:threateye/core/network/api_client.dart';
import 'package:threateye/core/network/dio_factory.dart';
import 'package:threateye/core/network/interceptors/auth_interceptor.dart';
import 'package:threateye/core/services/offline_queue_service.dart';
import 'package:threateye/core/services/secure_storage_service.dart';
import 'package:threateye/core/services/websocket_manager_service.dart';
import 'package:threateye/features/alerts/data/datasources/alerts_remote_data_source.dart';
import 'package:threateye/features/alerts/data/repositories/alerts_repository_impl.dart';
import 'package:threateye/features/alerts/domain/repositories/alerts_repository.dart';
import 'package:threateye/features/alerts/domain/usecases/get_alert_by_id_usecase.dart';
import 'package:threateye/features/alerts/domain/usecases/get_alerts_usecase.dart';
import 'package:threateye/features/alerts/domain/usecases/update_alert_status_usecase.dart';
import 'package:threateye/features/alerts/presentation/manager/alerts_cubit.dart';
import 'package:threateye/features/auth/data/datasources/auth_remote_data_source.dart';
import 'package:threateye/features/auth/data/repositories/auth_repository_impl.dart';
import 'package:threateye/features/auth/domain/repositories/auth_repository.dart';
import 'package:threateye/features/auth/domain/usecases/login_usecase.dart';
import 'package:threateye/features/auth/domain/usecases/logout_usecase.dart';
import 'package:threateye/features/auth/domain/usecases/refresh_token_usecase.dart';
import 'package:threateye/features/dashboard/data/datasources/dashboard_remote_data_source.dart';
import 'package:threateye/features/dashboard/data/repositories/dashboard_repository_impl.dart';
import 'package:threateye/features/dashboard/domain/repositories/dashboard_repository.dart';
import 'package:threateye/features/dashboard/domain/usecases/get_dashboard_summary_usecase.dart';
import 'package:threateye/features/dashboard/presentation/manager/dashboard_cubit.dart';
// ── Phase 4 ────────────────────────────────────────────────────────────────────
import 'package:threateye/features/decision/data/datasources/decision_remote_data_source.dart';
import 'package:threateye/features/decision/data/repositories/decision_repository_impl.dart';
import 'package:threateye/features/decision/domain/repositories/decision_repository.dart';
import 'package:threateye/features/decision/domain/usecases/get_decision_history_usecase.dart';
import 'package:threateye/features/decision/domain/usecases/submit_decision_usecase.dart';
import 'package:threateye/features/decision/presentation/manager/decision_cubit.dart';
import 'package:threateye/features/firewall/data/datasources/firewall_remote_data_source.dart';
import 'package:threateye/features/firewall/data/repositories/firewall_repository_impl.dart';
import 'package:threateye/features/firewall/domain/repositories/firewall_repository.dart';
import 'package:threateye/features/firewall/domain/usecases/block_ip_usecase.dart';
import 'package:threateye/features/firewall/domain/usecases/get_blocked_ips_usecase.dart';
import 'package:threateye/features/firewall/domain/usecases/unblock_ip_usecase.dart';
import 'package:threateye/features/firewall/presentation/manager/firewall_cubit.dart';
// ── Phase 5 ────────────────────────────────────────────────────────────────────
// Notifications feature (data source, repositories, use cases, cubits)
import 'package:threateye/features/notifications/data/datasources/notification_remote_data_source.dart';
import 'package:threateye/features/notifications/data/repositories/notification_repository_impl.dart';
import 'package:threateye/features/notifications/data/repositories/notifications_repository_impl.dart';
import 'package:threateye/features/notifications/domain/repositories/notification_repository.dart';
import 'package:threateye/features/notifications/domain/repositories/notifications_repository.dart';
import 'package:threateye/features/notifications/domain/usecases/get_notifications_usecase.dart';
import 'package:threateye/features/notifications/domain/usecases/register_device_usecase.dart';
import 'package:threateye/features/notifications/presentation/cubit/notifications_cubit.dart';
import 'package:threateye/features/notifications/presentation/manager/notification_cubit.dart';

/// Global service locator.
final GetIt sl = GetIt.instance;

/// Registers all dependencies in the correct order.
/// Called once in [main] before [runApp].
Future<void> init() async {
  // ── 1. Core services ───────────────────────────────────────────────────────
  // SecureStorageService is a singleton — one encrypted storage handle app-wide.
  sl.registerLazySingleton<SecureStorageService>(() => SecureStorageService());

  // ── 2. Raw Dio (NO AuthInterceptor) ───────────────────────────────────────
  // Used exclusively by AuthRemoteDataSource so login/refresh/logout calls
  // never pass through the AuthInterceptor and cannot cause a refresh loop.
  final rawDio = DioFactory.createRawDio();

  // ── 3. Auth data source (uses raw Dio) ────────────────────────────────────
  sl.registerLazySingleton<AuthRemoteDataSource>(
    () => AuthRemoteDataSourceImpl(rawDio, sl<SecureStorageService>()),
  );

  // ── 4. AuthInterceptor (created before authenticated Dio) ─────────────────
  final authInterceptor = AuthInterceptor(
    storage: sl<SecureStorageService>(),
    authDataSource: sl<AuthRemoteDataSource>(),
  );
  sl.registerSingleton<AuthInterceptor>(authInterceptor);

  // ── 5. Authenticated Dio (with AuthInterceptor) ───────────────────────────
  final authenticatedDio = DioFactory.createDio(
    authInterceptor: authInterceptor,
  );
  // Back-inject parent Dio into the interceptor so it can retry requests.
  authInterceptor.init(authenticatedDio);
  sl.registerSingleton<Dio>(authenticatedDio);

  sl.registerLazySingleton<ApiClient>(() => ApiClient(sl<Dio>()));

  // ── 7. Auth repository ────────────────────────────────────────────────────
  sl.registerLazySingleton<AuthRepository>(
    () => AuthRepositoryImpl(sl<AuthRemoteDataSource>()),
  );

  // ── 8. Auth use cases ─────────────────────────────────────────────────────
  // registerFactory = new instance per resolution — correct for use cases.
  sl.registerFactory<LoginUseCase>(() => LoginUseCase(sl<AuthRepository>()));
  sl.registerFactory<LogoutUseCase>(() => LogoutUseCase(sl<AuthRepository>()));
  sl.registerFactory<RefreshTokenUseCase>(
    () => RefreshTokenUseCase(sl<AuthRepository>()),
  );

  // ══════════════════════════════════════════════════════════════════════════
  // Phase 3 — Dashboard & Alerts API Integration
  // ══════════════════════════════════════════════════════════════════════════

  // ── 9. Dashboard data source ──────────────────────────────────────────────
  sl.registerLazySingleton<DashboardRemoteDataSource>(
    () => DashboardRemoteDataSourceImpl(sl<ApiClient>()),
  );

  // ── 10. Dashboard repository ──────────────────────────────────────────────
  sl.registerLazySingleton<DashboardRepository>(
    () => DashboardRepositoryImpl(sl<DashboardRemoteDataSource>()),
  );

  // ── 11. Dashboard use case ────────────────────────────────────────────────
  sl.registerFactory<GetDashboardSummaryUseCase>(
    () => GetDashboardSummaryUseCase(sl<DashboardRepository>()),
  );

  // ── 12. DashboardCubit (factory — one fresh instance per BlocProvider) ────
  sl.registerFactory<DashboardCubit>(
    () => DashboardCubit(
      getDashboardSummaryUseCase: sl<GetDashboardSummaryUseCase>(),
    ),
  );

  // ── 13. Alerts data source ────────────────────────────────────────────────
  sl.registerLazySingleton<AlertsRemoteDataSource>(
    () => AlertsRemoteDataSourceImpl(sl<ApiClient>()),
  );

  // ── 14. Alerts repository ─────────────────────────────────────────────────
  sl.registerLazySingleton<AlertsRepository>(
    () => AlertsRepositoryImpl(sl<AlertsRemoteDataSource>()),
  );

  // ── 15. Alerts use cases ──────────────────────────────────────────────────
  sl.registerFactory<GetAlertsUseCase>(
    () => GetAlertsUseCase(sl<AlertsRepository>()),
  );
  sl.registerFactory<GetAlertByIdUseCase>(
    () => GetAlertByIdUseCase(sl<AlertsRepository>()),
  );
  sl.registerFactory<UpdateAlertStatusUseCase>(
    () => UpdateAlertStatusUseCase(sl<AlertsRepository>()),
  );

  // ── 16. AlertsCubit (factory — one fresh instance per BlocProvider) ───────
  sl.registerFactory<AlertsCubit>(
    () => AlertsCubit(
      getAlertsUseCase:         sl<GetAlertsUseCase>(),
      getAlertByIdUseCase:      sl<GetAlertByIdUseCase>(),
      updateAlertStatusUseCase: sl<UpdateAlertStatusUseCase>(),
      // Phase 5: inject the singleton WS service so every cubit instance
      // shares the same connection and broadcast stream.
      webSocketManagerService:  sl<WebSocketManagerService>(),
    ),
  );

  // ══════════════════════════════════════════════════════════════════════════
  // Phase 4 — Decision Flow & Firewall Management
  // ══════════════════════════════════════════════════════════════════════════

  // ── 17. Decision data source ──────────────────────────────────────────────
  sl.registerLazySingleton<DecisionRemoteDataSource>(
    () => DecisionRemoteDataSourceImpl(sl<ApiClient>()),
  );

  // ── 18. Decision repository ───────────────────────────────────────────────
  sl.registerLazySingleton<DecisionRepository>(
    () => DecisionRepositoryImpl(sl<DecisionRemoteDataSource>()),
  );

  // ── 19. Decision use cases ────────────────────────────────────────────────
  sl.registerFactory<SubmitDecisionUseCase>(
    () => SubmitDecisionUseCase(sl<DecisionRepository>()),
  );
  sl.registerFactory<GetDecisionHistoryUseCase>(
    () => GetDecisionHistoryUseCase(sl<DecisionRepository>()),
  );

  // ── 20. DecisionCubit (factory — fresh instance per BlocProvider) ─────────
  sl.registerFactory<DecisionCubit>(
    () => DecisionCubit(
      getDecisionHistoryUseCase: sl<GetDecisionHistoryUseCase>(),
      submitDecisionUseCase:     sl<SubmitDecisionUseCase>(),
      // Phase 6: inject offline queue so the cubit can enqueue decisions
      // that fail due to NetworkFailure instead of emitting an error.
      offlineQueue:              sl<OfflineQueueService>(),
    ),
  );

  // ── 21. Firewall data source ──────────────────────────────────────────────
  sl.registerLazySingleton<FirewallRemoteDataSource>(
    () => FirewallRemoteDataSourceImpl(sl<ApiClient>()),
  );

  // ── 22. Firewall repository ───────────────────────────────────────────────
  sl.registerLazySingleton<FirewallRepository>(
    () => FirewallRepositoryImpl(sl<FirewallRemoteDataSource>()),
  );

  // ── 23. Firewall use cases ────────────────────────────────────────────────
  sl.registerFactory<GetBlockedIpsUseCase>(
    () => GetBlockedIpsUseCase(sl<FirewallRepository>()),
  );
  sl.registerFactory<BlockIpUseCase>(
    () => BlockIpUseCase(sl<FirewallRepository>()),
  );
  sl.registerFactory<UnblockIpUseCase>(
    () => UnblockIpUseCase(sl<FirewallRepository>()),
  );

  // ── 24. FirewallCubit (factory — fresh instance per BlocProvider) ─────────
  sl.registerFactory<FirewallCubit>(
    () => FirewallCubit(
      getBlockedIpsUseCase: sl<GetBlockedIpsUseCase>(),
      blockIpUseCase:       sl<BlockIpUseCase>(),
      unblockIpUseCase:     sl<UnblockIpUseCase>(),
    ),
  );

  // ══════════════════════════════════════════════════════════════════════════
  // Phase 5 — Real-Time Systems (WebSocket + Local Notifications)
  // ══════════════════════════════════════════════════════════════════════════

  // ── 25. WebSocketManagerService (singleton — one connection for the app) ───
  // Must be registered BEFORE AlertsCubit factory so sl<> resolves it.
  // LocalNotificationService is a static class — no DI registration needed.
  sl.registerLazySingleton<WebSocketManagerService>(
    () => WebSocketManagerService(sl<SecureStorageService>()),
  );

  // ── 26. Notifications: shared data source ────────────────────────────────
  // Single lazy singleton shared by both the device-registration pipeline
  // (NotificationRepository) and the fetch-notifications pipeline
  // (NotificationsRepository).
  sl.registerLazySingleton<NotificationRemoteDataSource>(
    () => NotificationRemoteDataSourceImpl(sl<ApiClient>()),
  );

  // ── 27. Notifications: device-registration repository + use case ─────────
  sl.registerLazySingleton<NotificationRepository>(
    () => NotificationRepositoryImpl(sl<NotificationRemoteDataSource>()),
  );
  sl.registerFactory<RegisterDeviceUseCase>(
    () => RegisterDeviceUseCase(sl<NotificationRepository>()),
  );

  // ── 28. NotificationCubit (manager) — handles device registration ────────
  sl.registerFactory<NotificationCubit>(
    () => NotificationCubit(registerDeviceUseCase: sl<RegisterDeviceUseCase>()),
  );

  // ── 29. Notifications: fetch-notifications repository + use case ─────────
  sl.registerLazySingleton<NotificationsRepository>(
    () => NotificationsRepositoryImpl(sl<NotificationRemoteDataSource>()),
  );
  sl.registerFactory<GetNotificationsUseCase>(
    () => GetNotificationsUseCase(sl<NotificationsRepository>()),
  );

  // ── 30. NotificationsCubit (cubit) — loads notification list ────────────
  sl.registerFactory<NotificationsCubit>(
    () => NotificationsCubit(
      getNotificationsUseCase: sl<GetNotificationsUseCase>(),
    ),
  );
  // ══════════════════════════════════════════════════════════════════════════
  // Phase 6 — Production Hardening
  // ══════════════════════════════════════════════════════════════════════════

  // ── 26. OfflineQueueService (singleton — survives app restarts via prefs) ──
  // Registered before DecisionCubit factory so sl<> resolves it correctly.
  // init() is called immediately to attach SharedPreferences and the
  // connectivity listener; it also flushes any decisions left from the
  // previous app session.
  sl.registerLazySingleton<OfflineQueueService>(
    () => OfflineQueueService(sl<DecisionRemoteDataSource>()),
  );
  // Eagerly initialise so the connectivity listener is active from app start.
  await sl<OfflineQueueService>().init();
}

