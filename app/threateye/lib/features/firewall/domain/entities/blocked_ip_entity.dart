/// Represents a single blocked IP entry in the SOC firewall.
class BlockedIpEntity {
  final String  id;
  final String  ipAddress;
  final String  reason;

  /// ISO-8601 timestamp string when the block was applied.
  final String  blockedAt;

  /// Username / identifier of the analyst who applied the block.
  final String? blockedBy;

  /// Optional expiry timestamp. `null` means the block is indefinite.
  final String? expiresAt;

  const BlockedIpEntity({
    required this.id,
    required this.ipAddress,
    required this.reason,
    required this.blockedAt,
    this.blockedBy,
    this.expiresAt,
  });
}
