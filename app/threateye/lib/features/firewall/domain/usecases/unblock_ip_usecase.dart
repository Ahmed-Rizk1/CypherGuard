import 'package:dartz/dartz.dart';
import 'package:threateye/core/error/failures.dart';
import '../repositories/firewall_repository.dart';

/// Removes a blocked IP entry from the SOC firewall.
class UnblockIpUseCase {
  final FirewallRepository repository;

  UnblockIpUseCase(this.repository);

  Future<Either<Failure, void>> call(String ipAddress) =>
      repository.unblockIp(ipAddress);
}
