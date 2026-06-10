import 'package:dartz/dartz.dart';
import 'package:threateye/core/error/failures.dart';
import 'package:threateye/core/network/paginated_response.dart';
import '../entities/blocked_ip_entity.dart';
import '../repositories/firewall_repository.dart';

/// Retrieves a cursor-paginated list of currently blocked IPs.
class GetBlockedIpsUseCase {
  final FirewallRepository repository;

  GetBlockedIpsUseCase(this.repository);

  Future<Either<Failure, PaginatedResponse<BlockedIpEntity>>> call({
    String? cursor,
  }) =>
      repository.getBlockedIps(cursor: cursor);
}
