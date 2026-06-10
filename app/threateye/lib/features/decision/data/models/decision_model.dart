import '../../domain/entities/decision_entity.dart';

/// Data-layer model for a SOC decision.
///
/// Extends [DecisionEntity] so it IS-A entity, matching the pattern used by
/// [AttackAlertModel] throughout the codebase.
class DecisionModel extends DecisionEntity {
  const DecisionModel({
    required super.id,
    required super.alertId,
    required super.action,
    required super.decidedAt,
    super.note,
    super.analystId,
  });

  /// Deserialises from the SecureNet API response.
  ///
  /// Expected JSON shape (single item inside `data` array or object):
  /// ```json
  /// {
  ///   "id":          "d-001",
  ///   "alert_id":    "a-009",
  ///   "action":      "APPROVE",
  ///   "decided_at":  "2025-05-17T18:42:00Z",
  ///   "note":        "Confirmed false positive.",
  ///   "analyst_id":  "soc-analyst-1"
  /// }
  /// ```
  factory DecisionModel.fromJson(Map<String, dynamic> json) {
    return DecisionModel(
      id:         json['id']?.toString()          ?? '',
      alertId:    json['alert_id']?.toString()    ?? '',
      action:     DecisionAction.fromString(
                    (json['action'] as String?)    ?? 'ESCALATE',
                  ),
      decidedAt:  json['decided_at']              ?? json['created_at'] ?? '',
      note:       json['note']        as String?,
      analystId:  json['analyst_id'] as String?,
    );
  }

  /// Serialises to JSON (used when submitting a new decision via POST).
  Map<String, dynamic> toJson() => {
    'id':          id,
    'alert_id':    alertId,
    'action':      action.toApiString(),
    'decided_at':  decidedAt,
    if (note       != null) 'note':       note,
    if (analystId  != null) 'analyst_id': analystId,
  };
}
