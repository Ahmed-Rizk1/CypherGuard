class AttackAlertEntity {
  final String id;
  final String attackType;
  final String severity;
  final String status;
  final String time;
  final String sourceIp;

  /// Optional: human-readable description of the alert (from API `description`).
  final String? description;

  /// Optional: destination / target IP address (from API `dst_ip`).
  final String? targetIp;

  AttackAlertEntity({
    required this.id,
    required this.attackType,
    required this.severity,
    required this.status,
    required this.time,
    required this.sourceIp,
    this.description,
    this.targetIp,
  });
}
