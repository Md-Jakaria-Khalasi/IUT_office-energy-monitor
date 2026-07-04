import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import 'animated_counter.dart';
import 'glass_card.dart';

/// Premium stat tile used in the header summary.
class StatCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final num value;
  final String suffix;
  final String prefix;
  final int fractionDigits;
  final Color accent;
  final String? helper;

  const StatCard({
    super.key,
    required this.icon,
    required this.label,
    required this.value,
    required this.accent,
    this.suffix = '',
    this.prefix = '',
    this.fractionDigits = 0,
    this.helper,
  });

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      padding: const EdgeInsets.all(AppSpacing.xl),
      shadows: [BoxShadow(color: accent.withValues(alpha: 0.10), blurRadius: 24, spreadRadius: -4), ...AppGlow.soft()],
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: accent.withValues(alpha: 0.16),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: accent.withValues(alpha: 0.4), width: 1),
                ),
                child: Icon(icon, color: accent, size: 22),
              ),
              const Spacer(),
              if (helper != null)
                Text(
                  helper!,
                  style: AppText.caption(context),
                ),
            ],
          ),
          const SizedBox(height: AppSpacing.lg),
          AnimatedCounter(
            value: value,
            fractionDigits: fractionDigits,
            suffix: suffix,
            prefix: prefix,
            style: AppText.metric(context, size: 30),
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(label, style: AppText.bodyMuted(context)),
        ],
      ),
    );
  }
}