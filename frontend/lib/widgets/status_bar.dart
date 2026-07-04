import 'package:flutter/material.dart';

import '../services/realtime_service.dart';
import '../theme/app_theme.dart';
import 'glass_card.dart';

/// Horizontal status pill row that sits under the header. Mirrors the
/// "Live Status (Connected)" spec — a continuously updating badge so the
/// user can see at a glance that the system is healthy.
class StatusBar extends StatelessWidget {
  final WsStatus wsStatus;
  final DateTime? lastUpdate;

  const StatusBar({super.key, required this.wsStatus, required this.lastUpdate});

  Color get _wsColor => switch (wsStatus) {
        WsStatus.connected => AppColors.success,
        WsStatus.connecting => AppColors.warning,
        WsStatus.disconnected => AppColors.danger,
      };

  String get _wsLabel => switch (wsStatus) {
        WsStatus.connected => 'WebSocket: Connected',
        WsStatus.connecting => 'WebSocket: Connecting…',
        WsStatus.disconnected => 'WebSocket: Disconnected',
      };

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.xxl,
        vertical: AppSpacing.lg,
      ),
      shadows: AppGlow.soft(),
      child: Row(
        children: [
          _Pill(color: _wsColor, label: _wsLabel, pulse: wsStatus == WsStatus.connected),
          const SizedBox(width: AppSpacing.md),
          const _Pill(color: AppColors.success, label: 'API: Online', pulse: false),
          const SizedBox(width: AppSpacing.md),
          const _Pill(color: AppColors.info, label: 'Updates: 2s', pulse: true),
          const Spacer(),
          const Icon(Icons.bolt, color: AppColors.primary, size: 18),
          const SizedBox(width: 6),
          Text(
            'LIVE',
            style: AppText.caption(context).copyWith(color: AppColors.primary, letterSpacing: 1.4),
          ),
        ],
      ),
    );
  }
}

class _Pill extends StatefulWidget {
  final Color color;
  final String label;
  final bool pulse;
  const _Pill({required this.color, required this.label, required this.pulse});

  @override
  State<_Pill> createState() => _PillState();
}

class _PillState extends State<_Pill> with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 1400))..repeat(reverse: true);

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final dot = AnimatedBuilder(
      animation: _ctrl,
      builder: (_, __) {
        final t = widget.pulse ? _ctrl.value : 1.0;
        return Container(
          width: 8,
          height: 8,
          decoration: BoxDecoration(
            color: widget.color.withValues(alpha: 0.5 + 0.5 * t),
            shape: BoxShape.circle,
            boxShadow: widget.pulse
                ? [BoxShadow(color: widget.color.withValues(alpha: 0.6), blurRadius: 8)]
                : null,
          ),
        );
      },
    );
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: AppColors.surfaceAlt,
        border: Border.all(color: AppColors.border),
        borderRadius: BorderRadius.circular(AppRadius.pill),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          dot,
          const SizedBox(width: 8),
          Text(widget.label, style: AppText.body(context).copyWith(fontSize: 12)),
        ],
      ),
    );
  }
}