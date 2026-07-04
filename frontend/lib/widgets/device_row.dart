import 'package:flutter/material.dart';

import '../models/device.dart';
import '../theme/app_theme.dart';

/// Single device row shown inside a room card. Icon + name + id + watts
/// on the left, a glowing custom toggle on the right. Pure paint — no
/// Material `Switch` because we want the brand glow.
class DeviceRow extends StatelessWidget {
  final Device device;
  final ValueChanged<bool> onToggle;

  const DeviceRow({super.key, required this.device, required this.onToggle});

  IconData get _icon => switch (device.type.toLowerCase()) {
        'light' => Icons.lightbulb_outline,
        'fan' => Icons.toys_outlined,
        'ac' || 'air_conditioner' => Icons.ac_unit,
        _ => Icons.power_settings_new,
      };

  @override
  Widget build(BuildContext context) {
    final on = device.isOn;
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.lg,
        vertical: AppSpacing.md,
      ),
      decoration: BoxDecoration(
        color: on
            ? AppColors.primary.withValues(alpha: 0.06)
            : AppColors.surfaceAlt,
        borderRadius: BorderRadius.circular(AppRadius.inner),
        border: Border.all(
          color: on
              ? AppColors.primary.withValues(alpha: 0.45)
              : AppColors.border,
        ),
      ),
      child: Row(
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: on
                  ? AppColors.primary.withValues(alpha: 0.18)
                  : AppColors.surfaceHigh,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(
                color: on
                    ? AppColors.primary.withValues(alpha: 0.5)
                    : AppColors.border,
              ),
            ),
            child: Icon(
              _icon,
              size: 20,
              color: on ? AppColors.primary : AppColors.textMuted,
            ),
          ),
          const SizedBox(width: AppSpacing.lg),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Row(
                  children: [
                    Flexible(
                      child: Text(
                        device.name,
                        style: AppText.body(context),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      '#${device.id}',
                      style: AppText.caption(context),
                    ),
                  ],
                ),
                const SizedBox(height: 2),
                Row(
                  children: [
                    Icon(
                      Icons.bolt,
                      size: 12,
                      color: on ? AppColors.primary : AppColors.textMuted,
                    ),
                    Text(
                      '${device.powerConsumption.toStringAsFixed(0)} W',
                      style: AppText.caption(context).copyWith(
                        color: on ? AppColors.primary : AppColors.textMuted,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: on
                            ? AppColors.success.withValues(alpha: 0.18)
                            : AppColors.surfaceHigh,
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        on ? 'ON' : 'OFF',
                        style: AppText.caption(context).copyWith(
                          color: on ? AppColors.success : AppColors.textMuted,
                          fontSize: 10,
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(width: AppSpacing.md),
          _GlowSwitch(value: on, onChanged: onToggle),
        ],
      ),
    );
  }
}

class _GlowSwitch extends StatelessWidget {
  final bool value;
  final ValueChanged<bool> onChanged;
  const _GlowSwitch({required this.value, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => onChanged(!value),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 220),
        curve: Curves.easeOutCubic,
        width: 48,
        height: 26,
        padding: const EdgeInsets.all(3),
        decoration: BoxDecoration(
          color: value
              ? AppColors.primary.withValues(alpha: 0.35)
              : AppColors.surfaceHigh,
          borderRadius: BorderRadius.circular(AppRadius.pill),
          border: Border.all(
            color: value
                ? AppColors.primary.withValues(alpha: 0.7)
                : AppColors.border,
          ),
          boxShadow: value
              ? const [BoxShadow(color: AppColors.glowCyan, blurRadius: 14, spreadRadius: -2)]
              : null,
        ),
        child: AnimatedAlign(
          duration: const Duration(milliseconds: 220),
          curve: Curves.easeOutCubic,
          alignment: value ? Alignment.centerRight : Alignment.centerLeft,
          child: Container(
            width: 18,
            height: 18,
            decoration: BoxDecoration(
              color: value ? AppColors.primary : AppColors.textMuted,
              shape: BoxShape.circle,
              boxShadow: value
                  ? [BoxShadow(color: AppColors.primary.withValues(alpha: 0.6), blurRadius: 8)]
                  : null,
            ),
          ),
        ),
      ),
    );
  }
}