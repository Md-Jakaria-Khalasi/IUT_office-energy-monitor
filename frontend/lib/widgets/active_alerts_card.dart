import 'package:flutter/material.dart';

import '../models/device.dart';
import '../theme/app_theme.dart';
import 'alert_list.dart';
import 'glass_card.dart';

/// Scrollable card listing active alerts. Empty state renders a friendly
/// "All clear" message with a green pulse dot.
///
/// Header includes severity badges (Critical / Warning / Info) with live
/// counts so the operator can see the alert mix at a glance.
class ActiveAlertsCard extends StatelessWidget {
  final List<Alert> alerts;
  const ActiveAlertsCard({super.key, required this.alerts});

  @override
  Widget build(BuildContext context) {
    final sorted = [...alerts]
      ..sort((a, b) {
        // Unacknowledged first, then newest first.
        if (a.acknowledged != b.acknowledged) {
          return a.acknowledged ? 1 : -1;
        }
        return b.createdAt.compareTo(a.createdAt);
      });

    final counts = _severityCounts(alerts);

    return GlassCard(
      padding: const EdgeInsets.all(AppSpacing.xxl),
      shadows: AppGlow.soft(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Text('ACTIVE ALERTS', style: AppText.sectionTitle(context)),
              const SizedBox(width: AppSpacing.sm),
              _CountBadge(count: alerts.length),
              const Spacer(),
              _SeverityDot(
                color: AppColors.danger,
                count: counts.critical,
                label: 'CRIT',
              ),
              const SizedBox(width: AppSpacing.sm),
              _SeverityDot(
                color: AppColors.warning,
                count: counts.warning,
                label: 'WARN',
              ),
              const SizedBox(width: AppSpacing.sm),
              _SeverityDot(
                color: AppColors.info,
                count: counts.info,
                label: 'INFO',
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.lg),
          if (sorted.isEmpty)
            const _EmptyState()
          else
            ConstrainedBox(
              constraints: const BoxConstraints(maxHeight: 340),
              child: Scrollbar(
                thumbVisibility: true,
                child: ListView.separated(
                  shrinkWrap: true,
                  padding: EdgeInsets.zero,
                  itemCount: sorted.length,
                  separatorBuilder: (_, __) => const Divider(
                    color: AppColors.border,
                    height: 1,
                  ),
                  itemBuilder: (_, i) => AlertList(alert: sorted[i]),
                ),
              ),
            ),
        ],
      ),
    );
  }

  static ({int critical, int warning, int info}) _severityCounts(
    List<Alert> list,
  ) {
    var c = 0;
    var w = 0;
    var i = 0;
    for (final a in list) {
      switch (a.severity.toLowerCase()) {
        case 'critical':
        case 'high':
          c++;
          break;
        case 'warning':
        case 'medium':
          w++;
          break;
        default:
          i++;
      }
    }
    return (critical: c, warning: w, info: i);
  }
}

class _CountBadge extends StatelessWidget {
  final int count;
  const _CountBadge({required this.count});

  @override
  Widget build(BuildContext context) {
    final isEmpty = count == 0;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: isEmpty
            ? AppColors.success.withValues(alpha: 0.15)
            : AppColors.danger.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        '$count',
        style: AppText.bodyMuted(context).copyWith(
          fontSize: 11,
          fontWeight: FontWeight.w700,
          color: isEmpty ? AppColors.success : AppColors.danger,
        ),
      ),
    );
  }
}

class _SeverityDot extends StatelessWidget {
  final Color color;
  final int count;
  final String label;
  const _SeverityDot({
    required this.color,
    required this.count,
    required this.label,
  });

  @override
  Widget build(BuildContext context) {
    if (count == 0) {
      return Opacity(
        opacity: 0.4,
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.5),
                shape: BoxShape.circle,
              ),
            ),
            const SizedBox(width: 4),
            Text(
              '0 $label',
              style: AppText.caption(context).copyWith(
                color: color,
                fontSize: 10,
                fontWeight: FontWeight.w700,
                letterSpacing: 0.8,
              ),
            ),
          ],
        ),
      );
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(AppRadius.pill),
        border: Border.all(color: color.withValues(alpha: 0.4), width: 1),
        boxShadow: [
          BoxShadow(
            color: color.withValues(alpha: 0.3),
            blurRadius: 8,
            spreadRadius: -2,
          ),
        ],
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 7,
            height: 7,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 4),
          Text(
            '$count $label',
            style: AppText.body(context).copyWith(
              fontSize: 10,
              color: color,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.8,
            ),
          ),
        ],
      ),
    );
  }
}

class _EmptyState extends StatefulWidget {
  const _EmptyState();

  @override
  State<_EmptyState> createState() => _EmptyStateState();
}

class _EmptyStateState extends State<_EmptyState>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctl = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1500),
  )..repeat(reverse: true);

  @override
  void dispose() {
    _ctl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.xl),
      child: Row(
        children: [
          AnimatedBuilder(
            animation: _ctl,
            builder: (_, __) => Container(
              width: 10,
              height: 10,
              decoration: BoxDecoration(
                color: AppColors.success.withValues(
                  alpha: 0.5 + _ctl.value * 0.5,
                ),
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: AppColors.success.withValues(
                      alpha: 0.4 + _ctl.value * 0.4,
                    ),
                    blurRadius: 10,
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(width: AppSpacing.md),
          Text(
            'All clear — no active alerts',
            style: AppText.bodyMuted(context),
          ),
        ],
      ),
    );
  }
}