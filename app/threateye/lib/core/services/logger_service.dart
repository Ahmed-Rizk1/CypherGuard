import 'package:logger/logger.dart';

/// App-wide logger using the [logger] package.
/// Use this instead of [print] throughout the project.
class LoggerService {
  static final Logger _logger = Logger(
    printer: PrettyPrinter(
      methodCount: 2,
      errorMethodCount: 8,
      lineLength: 100,
      colors: true,
      printEmojis: true,
    ),
  );

  static void debug(String message) => _logger.d(message);
  static void info(String message) => _logger.i(message);
  static void warning(String message) => _logger.w(message);
  static void error(String message, [Object? err, StackTrace? st]) =>
      _logger.e(message, error: err, stackTrace: st);
}