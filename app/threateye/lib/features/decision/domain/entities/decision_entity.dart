/// A single SOC decision record as returned by the API.
///
/// Actions are represented as a [DecisionAction] enum so that Cubits and UI
/// can branch on value without stringly-typed comparisons.
class DecisionEntity {
  final String         id;
  final String         alertId;
  final DecisionAction action;

  /// ISO-8601 timestamp string (e.g. `"2025-05-17T18:42:00Z"`).
  final String         decidedAt;

  /// Optional analyst note or reason attached to the decision.
  final String?        note;

  /// Username / identifier of the analyst who made the decision.
  final String?        analystId;

  const DecisionEntity({
    required this.id,
    required this.alertId,
    required this.action,
    required this.decidedAt,
    this.note,
    this.analystId,
  });
}

/// The three valid decision actions the SOC analyst can take on an alert.
enum DecisionAction {
  approve,
  reject,
  escalate;

  /// Serialises to the API-expected uppercase string.
  String toApiString() => name.toUpperCase();

  /// Deserialises from the API string (case-insensitive).
  static DecisionAction fromString(String value) {
    switch (value.toUpperCase()) {
      case 'APPROVE':
        return DecisionAction.approve;
      case 'REJECT':
        return DecisionAction.reject;
      case 'ESCALATE':
        return DecisionAction.escalate;
      default:
        return DecisionAction.escalate;
    }
  }
}
