import '../../domain/entities/dashboard_summary_entity.dart';

abstract class DashboardState {}

class DashboardInitial extends DashboardState {}

class DashboardLoading extends DashboardState {}

class DashboardLoaded extends DashboardState {
  final DashboardSummaryEntity summary;

  DashboardLoaded(this.summary);
}

class DashboardError extends DashboardState {
  final String message;

  DashboardError(this.message);
}
