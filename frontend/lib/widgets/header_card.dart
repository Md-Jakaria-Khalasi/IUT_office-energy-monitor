import 'dart:async';
import 'package:flutter/material.dart';

import '../models/device.dart';
import '../theme/app_theme.dart';
import 'glass_card.dart';
import 'stat_card.dart';

/// Top-of-dashboard hero card.
///
/// Layout:
///   ┌──────────────────────────────────────────────────────┐
///   │ logo  Office Energy Monitor                  [LIVE]  │
///   │       Smart Building • Live Telemetry                │
///   ├──────────────────────────────────────────────────────┤
///   │ [TotalDevices] [Active] [LivePower] [Alerts] [Office]│
///   └──────────────────────────────────────────────────────┘
class HeaderCard extends StatefulWidget {
  final OverviewStats? overview;
  final DateTime now;

  const HeaderCard({
    super.key,
    required this.overview,
    required this.now,
  });

  @override
  State<HeaderCard> createState() => _HeaderCardState();
}

class _HeaderCardState extends State<HeaderCard> {
  late Timer _ticker;
  late DateTime _now;

  @override
  void initState() {
    super.initState();
    _now = widget.now;
    _ticker = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted) return;
      setState(() => _now = DateTime.now());
    });
  }

  @override
  void dispose() {
    _ticker.cancel();
    super.dispose();
  }

  String _dateLabel() {
    const months = [
      'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
    ];
    const weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    final w = weekdays[_now.weekday - 1];
    final m = months[_now.month - 1];
    final hh = _now.hour.toString().padLeft(2, '0');
    final mm = _now.minute.toString().padLeft(2, '0');
    final ss = _now.second.toString().padLeft(2, '0');
    return '$w, $m ${_now.day}, ${_now.year} • $hh:$mm:$ss';
  }

  ({String label, Color color, IconData icon}) _officeStatus() {
    final wd = _now.weekday;
    final h = _now.hour;
    if (wd == DateTime.saturday || wd == DateTime.sunday) {
      return (label: 'Weekend', color: AppColors.info, icon: Icons.weekend);
    }
    if (h >= 9 && h < 18) {
      return (label: 'Office Open',
          color: AppColors.success,
          icon: Icons.work_outline);
    }
    return (label: 'Office Closed',
        color: AppColors.warning,
        icon: Icons.do_not_disturb_on_outlined);
  }

  @override
  Widget build(BuildContext context) {
    final status = _officeStatus();
    final stats = widget.overview;
    final liveAlerts = stats?.activeAlerts ?? 0;

    final statsCards = <Widget>[
      StatCard(
        icon: Icons.devices_other,
        label: 'Total Devices',
        value: stats?.totalDevices ?? 0,
        accent: AppColors.primary,
      ),
      StatCard(
        icon: Icons.flash_on,
        label: 'Active Devices',
        value: stats?.activeDevices ?? 0,
        accent: AppColors.secondary,
        helper: stats == null
            ? null
            : stats.totalDevices == 0
                ? null
                : '${(stats.activeDevices / stats.totalDevices * 100).round()}%',
      ),
      StatCard(
        icon: Icons.bolt,
        label: 'Live Power',
        value: stats?.totalPower ?? 0,
        suffix: ' W',
        fractionDigits: 0,
        accent: AppColors.warning,
        helper: 'NOW',
      ),
      StatCard(
        icon: Icons.warning_amber_rounded,
        label: 'Active Alerts',
        value: liveAlerts,
        accent: liveAlerts == 0 ? AppColors.success : AppColors.danger,
      ),
      _OfficeStatusStat(
        label: 'Office Status',
        status: status,
        wallClock: _dateLabel(),
      ),
    ];

    return GlassCard(
      padding: const EdgeInsets.all(AppSpacing.xxl),
      shadows: AppGlow.cyan(blur: 36, spread: -6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Title row -------------------------------------------------------------
          LayoutBuilder(
            builder: (context, c) {
              final stacked = c.maxWidth < 720;
              final title = _Title(
                wallClock: _dateLabel(),
                status: status,
              );
              const liveBadge = _LiveBadge();
              if (stacked) {
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    title,
                    const SizedBox(height: AppSpacing.lg),
                    liveBadge,
                  ],
                );
              }
              return Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(child: title),
                  liveBadge,
                ],
              );
            },
          ),
          const SizedBox(height: AppSpacing.xxl),
          // Stats row ------------------------------------------------------------
          LayoutBuilder(
            builder: (context, c) {
              final wide = c.maxWidth > 1100;
              final tablet = c.maxWidth > 760 && c.maxWidth <= 1100;
              if (wide) {
                return Row(
                  children: [
                    for (var i = 0; i < statsCards.length; i++) ...[
                      Expanded(child: statsCards[i]),
                      if (i != statsCards.length - 1)
                        const SizedBox(width: AppSpacing.lg),
                    ],
                  ],
                );
              }
              final crossCount = tablet ? 3 : 2;
              return Wrap(
                spacing: AppSpacing.lg,
                runSpacing: AppSpacing.lg,
                children: statsCards
                    .map((s) => SizedBox(
                          width:
                              (c.maxWidth - (crossCount - 1) * AppSpacing.lg) /
                                  crossCount,
                          child: s,
                        ))
                    .toList(),
              );
            },
          ),
        ],
      ),
    );
  }
}

class _Title extends StatelessWidget {
  final String wallClock;
  final ({String label, Color color, IconData icon}) status;
  const _Title({required this.wallClock, required this.status});

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 56,
          height: 56,
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [AppColors.primary, AppColors.accentTeal],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            borderRadius: BorderRadius.circular(16),
            boxShadow: AppGlow.cyan(blur: 26, spread: -4),
          ),
          child: const Icon(Icons.energy_savings_leaf,
              color: Colors.black, size: 30),
        ),
        const SizedBox(width: AppSpacing.lg),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Office Energy Monitor',
                style: AppText.display(context),
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 4),
              Text(
                'Smart Building • Live Telemetry',
                style: AppText.bodyMuted(context),
              ),
              const SizedBox(height: AppSpacing.md),
              Wrap(
                spacing: AppSpacing.md,
                runSpacing: AppSpacing.sm,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  _Badge(
                    icon: Icons.access_time,
                    label: wallClock,
                    color: AppColors.textSecondary,
                  ),
                  _Badge(
                    icon: status.icon,
                    label: status.label,
                    color: status.color,
                    glow: true,
                  ),
                ],
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _Badge extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;
  final bool glow;
  const _Badge({
    required this.icon,
    required this.label,
    required this.color,
    this.glow = false,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
      decoration: BoxDecoration(
        color: AppColors.surfaceAlt,
        border: Border.all(color: AppColors.border),
        borderRadius: BorderRadius.circular(AppRadius.pill),
        boxShadow: glow
            ? [
                BoxShadow(
                    color: color.withValues(alpha: 0.35),
                    blurRadius: 14,
                    spreadRadius: -2),
              ]
            : null,
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 6),
          Text(
            label,
            style: AppText.body(context).copyWith(fontSize: 12, color: color),
          ),
        ],
      ),
    );
  }
}

/// Animated LIVE badge with pulse dot.
class _LiveBadge extends StatefulWidget {
  const _LiveBadge();

  @override
  State<_LiveBadge> createState() => _LiveBadgeState();
}

class _LiveBadgeState extends State<_LiveBadge>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1200),
  )..repeat(reverse: true);

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
      decoration: BoxDecoration(
        color: AppColors.primary.withValues(alpha: 0.12),
        border: Border.all(color: AppColors.primary.withValues(alpha: 0.55)),
        borderRadius: BorderRadius.circular(AppRadius.pill),
        boxShadow: AppGlow.cyan(blur: 18, spread: -2),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          AnimatedBuilder(
            animation: _ctrl,
            builder: (_, __) => Container(
              width: 9,
              height: 9,
              decoration: BoxDecoration(
                color: AppColors.primary
                    .withValues(alpha: 0.5 + 0.5 * _ctrl.value),
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: AppColors.primary.withValues(alpha: 0.65),
                    blurRadius: 10,
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(width: 8),
          Text(
            'LIVE',
            style: AppText.caption(context).copyWith(
              color: AppColors.primary,
              fontSize: 12,
              letterSpacing: 1.6,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}

/// Office status stat-tile variant — pill driven instead of a counter.
class _OfficeStatusStat extends StatelessWidget {
  final String label;
  final ({String label, Color color, IconData icon}) status;
  final String wallClock;
  const _OfficeStatusStat({
    required this.label,
    required this.status,
    required this.wallClock,
  });

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      padding: const EdgeInsets.all(AppSpacing.xl),
      shadows: [
        BoxShadow(
          color: status.color.withValues(alpha: 0.12),
          blurRadius: 24,
          spreadRadius: -4,
        ),
        ...AppGlow.soft(),
      ],
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
                  color: status.color.withValues(alpha: 0.16),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: status.color.withValues(alpha: 0.4),
                    width: 1,
                  ),
                ),
                child: Icon(status.icon, color: status.color, size: 22),
              ),
              const Spacer(),
              Text(
                'STATE',
                style: AppText.caption(context),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.lg),
          Text(
            status.label,
            style: AppText.metric(context, size: 22).copyWith(
              color: status.color,
            ),
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            label,
            style: AppText.bodyMuted(context),
          ),
          const SizedBox(height: 4),
          Text(
            wallClock,
            style: AppText.caption(context).copyWith(color: AppColors.textMuted),
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}