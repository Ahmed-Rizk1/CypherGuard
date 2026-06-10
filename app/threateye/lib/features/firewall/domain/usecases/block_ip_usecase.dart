import 'package:dartz/dartz.dart';
import 'package:threateye/core/error/failures.dart';
import '../entities/blocked_ip_entity.dart';
import '../repositories/firewall_repository.dart';

/// Adds a new blocked IP entry to the SOC firewall.
class BlockIpUseCase {
  final FirewallRepository repository;

  BlockIpUseCase(this.repository);

  Future<Either<Failure, BlockedIpEntity>> call({
    required String ipAddress,
    required String reason,
  }) =>
      repository.blockIp(
        ipAddress: ipAddress,
        reason:    reason,
      );
}
