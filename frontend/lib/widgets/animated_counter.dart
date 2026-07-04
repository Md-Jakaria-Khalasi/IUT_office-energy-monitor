import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Tweens a numeric value across changes. Used for the "Live Power" stat
/// tile so changes feel smooth instead of jittery.
class AnimatedCounter extends StatelessWidget {
  final num value;
  final Duration duration;
  final int fractionDigits;
  final TextStyle? style;
  final String suffix;
  final String prefix;

  const AnimatedCounter({
    super.key,
    required this.value,
    this.duration = const Duration(milliseconds: 600),
    this.fractionDigits = 0,
    this.style,
    this.suffix = '',
    this.prefix = '',
  });

  @override
  Widget build(BuildContext context) {
    return TweenAnimationBuilder<double>(
      tween: Tween<double>(begin: value.toDouble(), end: value.toDouble()),
      duration: duration,
      curve: Curves.easeOutCubic,
      builder: (context, v, _) {
        final formatted = v.toStringAsFixed(fractionDigits);
        return Text(
          '$prefix$formatted$suffix',
          style: style ?? AppText.metric(context),
        );
      },
    );
  }
}
