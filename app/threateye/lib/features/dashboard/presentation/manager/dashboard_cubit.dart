import 'package:flutter_bloc/flutter_bloc.dart';
import '../../domain/usecases/get_dashboard_summary_usecase.dart';
import 'dashboard_state.dart';

class DashboardCubit extends Cubit<DashboardState> {
  final GetDashboardSummaryUseCase getDashboardSummaryUseCase;

  DashboardCubit({required this.getDashboardSummaryUseCase})
      : super(DashboardInitial());

  Future<void> loadDashboard() async {
    emit(DashboardLoading());
    final result = await getDashboardSummaryUseCase();
    result.fold(
      (failure) => emit(DashboardError(failure.message)),
      (summary) => emit(DashboardLoaded(summary)),
    );
  }
}
