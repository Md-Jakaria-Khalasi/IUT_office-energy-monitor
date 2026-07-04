import 'package:flutter/material.dart';

import '../models/device.dart';
import '../theme/app_theme.dart';

/// Severity → accent color. Keep neutral on unknown values.
Color _severityColor(String s) {
  switch (s.toLowerCase()) {
    case 'critical':
    case 'high':
      return AppColors.danger;
    case 'warning':
    case 'medium':
      return AppColors.warning;
    case 'info':
    case 'low':
      return AppColors.info;
    default:
      return AppColors.primary;
  }
}

/// One row inside the Active Alerts card. Severity-colored indicator + message
/// + relative time + ack chip.
class AlertList extends StatelessWidget {
  final Alert alert;
  const AlertList({super.key, required this.alert});

  String _ago(DateTime t) {
    final d = DateTime.now().difference(t);
    if (d.inSeconds < 60) return '${d.inSeconds}s ago';
    if (d.inMinutes < 60) return '${d.inMinutes}m ago';
    if (d.inHours < 24) return '${d.inHours}h ago';
    return '${d.inDays}d ago';
  }

  @override
  Widget build(BuildContext context) {
    final c = _severityColor(alert.severity);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 3,
            height: 36,
            margin: const EdgeInsets.only(top: 2, right: AppSpacing.md),
            decoration: BoxDecoration(
              color: c,
              borderRadius: BorderRadius.circular(2),
              boxShadow: [
                BoxShadow(color: c.withValues(alpha: 0.6), blurRadius: 8),
              ],
            ),
          ),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  alert.message,
                  style: AppText.body(context),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 2),
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 6,
                        vertical: 2,
                      ),
                      decoration: BoxDecoration(
                        color: c.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        alert.severity.toUpperCase(),
                        style: AppText.bodyMuted(context).copyWith(
                          fontSize: 9,
                          color: c,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 1.1,
                        ),
                      ),
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    Text(
                      _ago(alert.createdAt),
                      style: AppText.bodyMuted(context).copyWith(fontSize: 11),
                    ),
                    if (alert.acknowledged) ...[
                      const SizedBox(width: AppSpacing.sm),
                      const Icon(
                        Icons.check_circle,
                        size: 12,
                        color: AppColors.success,
                      ),
                    ],
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}