/// Centralized asset path references.
/// Prevents hardcoding path strings across the app.
class AssetPaths {
  AssetPaths._();

  // Images
  static const String _imagesBase = 'assets/images';
  static const String appLogo = '$_imagesBase/app_logo.png';
  static const String appLogoIcon = '$_imagesBase/app_logo_icon.png';
  static const String splashBackground = '$_imagesBase/splash_bg.png';

  static const String _animationsBase = 'assets/animations';
  static const String loadingAnimation = '$_animationsBase/loading.json';
  static const String successAnimation = '$_animationsBase/success.json';
  static const String errorAnimation = '$_animationsBase/error.json';

  // Icons
  static const String _iconsBase = 'assets/icons';
  static const String shieldIcon = '$_iconsBase/shield.svg';
}
