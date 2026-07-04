// ignore_for_file: prefer_const_constructors
// AppText getters intentionally take a (currently unused) BuildContext parameter
// to keep the call-site API consistent (`AppText.title(context)`). Lifting them
// to top-level const TextStyles would require renaming every call site.

import 'package:flutter/material.dart';

/// Premium futuristic dark palette for the Office Energy Monitor dashboard.
///
/// Background is the deepest near-black navy, cards sit one step lighter,
/// borders are subtle blue-grey, and the cyan accent drives every active
/// state. Tokens are tuned for Material 3 contrast against the #08111D
/// scaffold.
class AppColors {
  // Surfaces
  static const background = Color(0xFF08111D); // page background
  static const surface = Color(0xFF111B28); // cards
  static const surfaceAlt = Color(0xFF152031); // nested rows / inputs
  static const surfaceHigh = Color(0xFF1A2740); // hover / active rows

  // Borders & dividers
  static const border = Color(0xFF223246); // hairline card border
  static const borderStrong = Color(0xFF2E4664); // hovered cards

  // Accents — locked to the design spec
  static const primary = Color(0xFF14D9FF); // cyan highlight
  static const secondary = Color(0xFF00B8D4); // secondary accent
  static const tertiary = Color(0xFF0EA5E9); // deeper cyan for shadows
  static const accentTeal = Color(0xFF00E676); // spark / success gradient

  // Status — locked to the design spec
  static const success = Color(0xFF00E676);
  static const warning = Color(0xFFFFC107);
  static const danger = Color(0xFFFF5252);
  static const info = Color(0xFF14D9FF);

  // Text
  static const textPrimary = Color(0xFFE6F1FF);
  static const textSecondary = Color(0xFF8AA1BD);
  static const textMuted = Color(0xFF5C7491);

  // Glow colors (used in shadows/box-shadows) — translucent versions of accents
  static const glowCyan = Color(0x4014D9FF);
  static const glowTeal = Color(0x4000E676);
  static const glowWarning = Color(0x40FFC107);
  static const glowDanger = Color(0x40FF5252);
}

/// Typography helpers. We use the system font stack so the bundle stays
/// self-contained (no Google Fonts download at runtime) while still
/// shipping a clean modern look.
class AppText {
  static const _family = 'Inter';

  static TextStyle display(BuildContext c) => const TextStyle(
        fontFamily: _family,
        fontSize: 30,
        fontWeight: FontWeight.w800,
        color: AppColors.textPrimary,
        letterSpacing: -0.6,
        height: 1.05,
      );

  static TextStyle title(BuildContext c) => const TextStyle(
        fontFamily: _family,
        fontSize: 20,
        fontWeight: FontWeight.w700,
        color: AppColors.textPrimary,
        letterSpacing: -0.2,
        height: 1.2,
      );

  static TextStyle sectionTitle(BuildContext c) => const TextStyle(
        fontFamily: _family,
        fontSize: 13,
        fontWeight: FontWeight.w700,
        color: AppColors.textPrimary,
        letterSpacing: 1.0,
        height: 1.2,
      );

  static TextStyle body(BuildContext c) => const TextStyle(
        fontFamily: _family,
        fontSize: 14,
        fontWeight: FontWeight.w500,
        color: AppColors.textPrimary,
        height: 1.4,
      );

  static TextStyle bodyMuted(BuildContext c) => const TextStyle(
        fontFamily: _family,
        fontSize: 14,
        fontWeight: FontWeight.w400,
        color: AppColors.textSecondary,
        height: 1.4,
      );

  static TextStyle caption(BuildContext c) => const TextStyle(
        fontFamily: _family,
        fontSize: 11,
        fontWeight: FontWeight.w600,
        color: AppColors.textMuted,
        letterSpacing: 0.6,
        height: 1.2,
      );

  static TextStyle metric(BuildContext c, {double size = 30}) => TextStyle(
        fontFamily: _family,
        fontSize: size,
        fontWeight: FontWeight.w800,
        color: AppColors.textPrimary,
        letterSpacing: -0.6,
        height: 1.0,
      );
}

/// Spacing tokens — keep the layout breathing at a consistent 24 px rhythm.
class AppSpacing {
  static const double xs = 4;
  static const double sm = 8;
  static const double md = 12;
  static const double lg = 16;
  static const double xl = 20;
  static const double xxl = 24;
  static const double xxxl = 32;
}

class AppRadius {
  static const double card = 20;
  static const double inner = 14;
  static const double pill = 999;
}

/// Decorative helpers — soft shadows and reusable containers.
class AppGlow {
  static List<BoxShadow> cyan({double blur = 28, double spread = -2}) => [
        BoxShadow(
          color: AppColors.glowCyan,
          blurRadius: blur,
          spreadRadius: spread,
        ),
      ];

  static List<BoxShadow> soft() => const [
        BoxShadow(
          color: Color(0x40000000),
          blurRadius: 18,
          offset: Offset(0, 8),
        ),
      ];

  static List<BoxShadow> teal({double blur = 28, double spread = -2}) => [
        BoxShadow(
          color: AppColors.glowTeal,
          blurRadius: blur,
          spreadRadius: spread,
        ),
      ];

  static List<BoxShadow> warning({double blur = 28, double spread = -2}) => [
        BoxShadow(
          color: AppColors.glowWarning,
          blurRadius: blur,
          spreadRadius: spread,
        ),
      ];

  static List<BoxShadow> danger({double blur = 28, double spread = -2}) => [
        BoxShadow(
          color: AppColors.glowDanger,
          blurRadius: blur,
          spreadRadius: spread,
        ),
      ];
}

class AppTheme {
  static ThemeData light() => _build(brightness: Brightness.light);
  static ThemeData dark() => _build(brightness: Brightness.dark);

  static ThemeData _build({required Brightness brightness}) {
    final isDark = brightness == Brightness.dark;
    final base = isDark ? ThemeData.dark() : ThemeData.light();

    final scheme = ColorScheme.fromSeed(
      seedColor: AppColors.primary,
      brightness: brightness,
    ).copyWith(
      surface: isDark ? AppColors.surface : Colors.white,
      onSurface: isDark ? AppColors.textPrimary : Colors.black87,
      primary: AppColors.primary,
      secondary: AppColors.secondary,
      error: AppColors.danger,
    );

    return base.copyWith(
      brightness: brightness,
      colorScheme: scheme,
      scaffoldBackgroundColor:
          isDark ? AppColors.background : const Color(0xFFF1F5F9),
      textTheme: base.textTheme.apply(
        bodyColor: isDark ? AppColors.textPrimary : Colors.black87,
        displayColor: isDark ? AppColors.textPrimary : Colors.black87,
      ),
      cardTheme: CardThemeData(
        color: AppColors.surface,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppRadius.card),
          side: const BorderSide(color: AppColors.border, width: 1),
        ),
      ),
      dividerColor: AppColors.border,
      iconTheme: const IconThemeData(color: AppColors.textSecondary),
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.background,
        foregroundColor: AppColors.textPrimary,
        elevation: 0,
        centerTitle: false,
      ),
      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) return Colors.black;
          return AppColors.textMuted;
        }),
        trackColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return AppColors.primary.withValues(alpha: 0.7);
          }
          return AppColors.surfaceHigh;
        }),
        trackOutlineColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return AppColors.primary;
          }
          return AppColors.border;
        }),
      ),
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: AppColors.primary,
        linearTrackColor: AppColors.surfaceAlt,
      ),
    );
  }
}