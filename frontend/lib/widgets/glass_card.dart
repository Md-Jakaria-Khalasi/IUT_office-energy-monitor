import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// A rounded surface with a subtle border used by every section in the
/// dashboard. Keep it dumb: just paint it.
class GlassCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final Color? color;
  final List<BoxShadow>? shadows;
  final VoidCallback? onTap;
  final BorderRadius? radius;

  const GlassCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(AppSpacing.xxl),
    this.color,
    this.shadows,
    this.onTap,
    this.radius,
  });

  @override
  Widget build(BuildContext context) {
    final card = AnimatedContainer(
      duration: const Duration(milliseconds: 220),
      curve: Curves.easeOutCubic,
      decoration: BoxDecoration(
        color: color ?? AppColors.surface,
        borderRadius: radius ?? BorderRadius.circular(AppRadius.card),
        border: Border.all(color: AppColors.border, width: 1),
        boxShadow: shadows ?? AppGlow.soft(),
      ),
      padding: padding,
      child: child,
    );
    if (onTap == null) return card;
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: radius ?? BorderRadius.circular(AppRadius.card),
        child: card,
      ),
    );
  }
}
