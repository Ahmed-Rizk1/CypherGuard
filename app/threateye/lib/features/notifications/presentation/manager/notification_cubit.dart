import 'dart:io';

import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:threateye/core/services/logger_service.dart';
import 'package:threateye/features/notifications/domain/entities/device_registration_entity.dart';
import 'package:threateye/features/notifications/domain/usecases/register_device_usecase.dart';

import 'notification_state.dart';

/// Manages device registration for push notifications.
///
/// **Sprint 2 — Firebase purge:**
/// All FCM (`firebase_core`, `firebase_messaging`) dependencies have been
/// removed. This cubit no longer requests FCM permission, calls `getToken()`,
/// listens to `onTokenRefresh`, or subscribes to `FirebaseMessaging.onMessage`.
///
/// The real-time alert pipeline is handled exclusively by:
///   • [WebSocketManagerService] — receives events from the backend.
///   • [LocalNotificationService] — surfaces them as OS notifications.
///
/// [RegisterDeviceUseCase] is kept so the backend can track the device;
/// the token field is left empty until a non-FCM mechanism is wired in.
///
/// All failures are logged and emitted as non-blocking states.
class NotificationCubit extends Cubit<NotificationState> {
  NotificationCubit({required RegisterDeviceUseCase registerDeviceUseCase})
      : _registerDeviceUseCase = registerDeviceUseCase,
        super(NotificationInitial());

  final RegisterDeviceUseCase _registerDeviceUseCase;

  // ── Public API ─────────────────────────────────────────────────────────────

  /// Entry point — call once after login.
  ///
  /// Does NOT throw. All errors are caught, logged, and emitted as states.
  Future<void> init() async {
    await _registerDevice();
  }

  // ── Private steps ──────────────────────────────────────────────────────────

  Future<void> _registerDevice() async {
    emit(NotificationRegistering());

    try {
      final entity = DeviceRegistrationEntity(
        fcmToken:   '',                                   // No FCM — token omitted.
        deviceName: _resolveDeviceName(),
        platform:   Platform.isAndroid ? 'android' : 'ios',
      );

      final result = await _registerDeviceUseCase(entity);

      result.fold(
        (failure) {
          LoggerService.error(
            '[Notifications] Device registration failed: ${failure.message}',
          );
          emit(NotificationRegistrationFailed(failure.message));
        },
        (_) {
          LoggerService.info('[Notifications] Device registered successfully.');
          emit(NotificationRegistered());
        },
      );
    } catch (e) {
      LoggerService.error('[Notifications] _registerDevice error: $e');
      emit(NotificationRegistrationFailed(e.toString()));
    }
  }

  // ── Helpers ────────────────────────────────────────────────────────────────

  String _resolveDeviceName() {
    if (Platform.isAndroid) return 'Android Device';
    if (Platform.isIOS)     return 'iOS Device';
    return 'Unknown Device';
  }
}
