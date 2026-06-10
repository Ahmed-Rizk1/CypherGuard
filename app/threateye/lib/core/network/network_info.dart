import 'package:connectivity_plus/connectivity_plus.dart';

/// Contract for checking network connectivity.
abstract class NetworkInfo {
  Future<bool> get isConnected;
}

/// Implementation using [connectivity_plus].
class NetworkInfoImpl implements NetworkInfo {
  final Connectivity connectivity;

  NetworkInfoImpl(this.connectivity);

  @override
  Future<bool> get isConnected async {
    final result = await connectivity.checkConnectivity();
    return result.any(
      (r) => r != ConnectivityResult.none,
    );
  }
}