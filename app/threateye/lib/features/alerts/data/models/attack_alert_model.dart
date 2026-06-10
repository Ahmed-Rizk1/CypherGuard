import '../../domain/entities/attack_alert_entity.dart';

class AttackAlertModel extends AttackAlertEntity {
  AttackAlertModel({
    required super.id,
    required super.attackType,
    required super.severity,
    required super.status,
    required super.time,
    required super.sourceIp,
    super.description,
    super.targetIp,
  });

  /// Deserializes from the SecureNet API response.
  ///
  /// Field names follow the API docs:
  ///  - `src_ip`      → [sourceIp]
  ///  - `dst_ip`      → [targetIp]
  ///  - `attack_type` → [attackType]
  ///  - `created_at`  → [time]
  factory AttackAlertModel.fromJson(Map<String, dynamic> json) {
    return AttackAlertModel(
      id:          json['id']?.toString() ?? '',
      attackType:  json['attack_type'] ?? json['attackType'] ?? '',
      severity:    json['severity']    ?? '',
      status:      json['status']      ?? '',
      time:        json['created_at']  ?? json['time'] ?? '',
      sourceIp:    json['src_ip']      ?? json['source_ip'] ?? '',
      description: json['description'] as String?,
      targetIp:    json['dst_ip']      ?? json['target_ip'] as String?,
    );
  }

  /// Serializes to JSON (used when sending data to the API).
  Map<String, dynamic> toJson() => {
    'id':          id,
    'attack_type': attackType,
    'severity':    severity,
    'status':      status,
    'created_at':  time,
    'src_ip':      sourceIp,
    if (description != null) 'description': description,
    if (targetIp    != null) 'dst_ip':      targetIp,
  };
}

