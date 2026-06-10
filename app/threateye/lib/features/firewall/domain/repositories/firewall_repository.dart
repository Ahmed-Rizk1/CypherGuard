import 'package:dartz/dartz.dart';
import 'package:threateye/core/error/failures.dart';
import 'package:threateye/core/network/paginated_response.dart';
import '../entities/blocked_ip_entity.dart';

/// Contract between Domain and Data layers for Firewall operations.
abstract class FirewallRepository {
  /// Retrieves a cursor-paginated list of currently blocked IPs.
  Future<Either<Failure, PaginatedResponse<BlockedIpEntity>>> getBlockedIps({
    String? cursor,
  });

  /// Blocks an IP address with a given reason.
  Future<Either<Failure, BlockedIpEntity>> blockIp({
    required String ipAddress,
    required String reason,
  });

  /// Removes the block on the given IP address.
  Future<Either<Failure, void>> unblockIp(String ipAddress);
}
