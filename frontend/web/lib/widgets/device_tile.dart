import 'package:flutter/material.dart';

import '../models/device.dart';
import '../theme/app_theme.dart';

class DeviceTile extends StatelessWidget {
  final Device device;
  final ValueChanged<bool> onToggle;

  const DeviceTile({super.key, required this.device, required this.onToggle});

  IconData get _icon =>
      device.type == 'fan' ? Icons.air : Icons.lightbulb_outline;

  @override
  Widget build(BuildContext context) {
    final active = device.isOn;
    return AnimatedContainer(
      duration: const Duration(milliseconds: 250),
      decoration: BoxDecoration(
        color: active
            ? AppColors.primary.withOpacity(0.10)
            : AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: active
              ? AppColors.primary.withOpacity(0.4)
              : Colors.white.withOpacity(0.05),
        ),
      ),
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: active
                  ? AppColors.primary.withOpacity(0.2)
                  : AppColors.surfaceAlt,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(
              _icon,
              color: active ? AppColors.primary : AppColors.textSecondary,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  device.name,
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                ),
                Text(
                  '${device.room} · ${device.powerConsumption.toStringAsFixed(0)} W',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: AppColors.textSecondary,
                      ),
                ),
              ],
            ),
          ),
          Switch.adaptive(
            value: active,
            onChanged: onToggle,
            activeColor: AppColors.primary,
          ),
        ],
      ),
    );
  }
}