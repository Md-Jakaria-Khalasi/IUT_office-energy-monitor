import 'package:flutter/material.dart';

import '../services/realtime_service.dart';
import '../theme/app_theme.dart';
import 'glass_card.dart';

/// Read-only card listing system facts: office status, simulation mode,
/// API status, WebSocket status, last-updated timestamp. Includes a header
/// health dot that reflects overall system health.
class SystemOverviewCard extends StatelessWidget {
  final WsStatus connection;
  final DateTime? lastUpdate;
  final bool officeOpen;

  const SystemOverviewCard({
    super.key,
    required this.connection,
    required this.lastUpdate,
    required this.officeOpen,
  });

  bool get _healthy =>
      connection == WsStatus.connected && (officeOpen || officeOpen == false);

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      padding: const EdgeInsets.all(AppSpacing.xxl),
      shadows: AppGlow.soft(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Text('SYSTEM OVERVIEW', style: AppText.sectionTitle(context)),
              const Spacer(),
              _HeaderHealthDot(
                color: _healthy ? AppColors.success : AppColors.warning,
                label: _healthy ? 'Healthy' : 'Degraded',
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.lg),
          _Row(
            icon: Icons.meeting_room_outlined,
            label: 'Office Status',
            child: _Pill(
              label: officeOpen ? 'Open' : 'Closed',
              color: officeOpen ? AppColors.success : AppColors.warning,
              pulse: officeOpen,
            ),
          ),
          const Divider(color: AppColors.border, height: AppSpacing.xl),
          const _Row(
            icon: Icons.auto_mode,
            label: 'Simulation Mode',
            child: _Pill(label: 'Auto', color: AppColors.primary),
          ),
          const Divider(color: AppColors.border, height: AppSpacing.xl),
          const _Row(
            icon: Icons.cloud_done_outlined,
            label: 'API Status',
            child: _Pill(label: 'Online', color: AppColors.success),
          ),
          const Divider(color: AppColors.border, height: AppSpacing.xl),
          _Row(
            icon: Icons.wifi_tethering,
            label: 'WebSocket',
            child: _Pill(
              label: _wsLabel(connection),
              color: _wsColor(connection),
              pulse: connection == WsStatus.connected,
            ),
          ),
          const Divider(color: AppColors.border, height: AppSpacing.xl),
          _Row(
            icon: Icons.schedule,
            label: 'Last Updated',
            child: Text(
              lastUpdate == null ? '—' : _shortAgo(lastUpdate!),
              style: AppText.bodyMuted(context).copyWith(
                fontFeatures: const [FontFeature.tabularFigures()],
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }

  static String _shortAgo(DateTime t) {
    final d = DateTime.now().difference(t);
    if (d.isNegative) return 'just now';
    if (d.inSeconds < 60) return '${d.inSeconds}s ago';
    if (d.inMinutes < 60) return '${d.inMinutes}m ago';
    return '${d.inHours}h ago';
  }

  static String _wsLabel(WsStatus s) {
    switch (s) {
      case WsStatus.connected:
        return 'Connected';
      case WsStatus.connecting:
        return 'Connecting…';
      case WsStatus.disconnected:
        return 'Offline';
    }
  }

  static Color _wsColor(WsStatus s) {
    switch (s) {
      case WsStatus.connected:
        return AppColors.success;
      case WsStatus.connecting:
        return AppColors.warning;
      case WsStatus.disconnected:
        return AppColors.danger;
    }
  }
}

class _HeaderHealthDot extends StatelessWidget {
  final Color color;
  final String label;
  const _HeaderHealthDot({required this.color, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        _PulseDot(color: color),
        const SizedBox(width: 6),
        Text(
          label.toUpperCase(),
          style: AppText.caption(context).copyWith(
            color: color,
            fontSize: 10,
            fontWeight: FontWeight.w700,
            letterSpacing: 1.2,
          ),
        ),
      ],
    );
  }
}

class _Row extends StatelessWidget {
  final IconData icon;
  final String label;
  final Widget child;
  const _Row({required this.icon, required this.label, required this.child});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 32,
          height: 32,
          decoration: BoxDecoration(
            color: AppColors.surfaceAlt,
            borderRadius: BorderRadius.circular(AppRadius.inner),
            border: Border.all(color: AppColors.border),
          ),
          alignment: Alignment.center,
          child: Icon(icon, size: 16, color: AppColors.textSecondary),
        ),
        const SizedBox(width: AppSpacing.md),
        Expanded(child: Text(label, style: AppText.body(context))),
        child,
      ],
    );
  }
}

class _Pill extends StatelessWidget {
  final String label;
  final Color color;
  final bool pulse;
  const _Pill({required this.label, required this.color, this.pulse = false});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(AppRadius.pill),
        border: Border.all(color: color.withValues(alpha: 0.4)),
        boxShadow: pulse
            ? [
                BoxShadow(
                  color: color.withValues(alpha: 0.25),
                  blurRadius: 10,
                  spreadRadius: -2,
                ),
              ]
            : null,
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (pulse) ...[
            _PulseDot(color: color),
            const SizedBox(width: 6),
          ],
          Text(
            label,
            style: AppText.bodyMuted(context).copyWith(
              color: color,
              fontSize: 11,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.8,
            ),
          ),
        ],
      ),
    );
  }
}

class _PulseDot extends StatefulWidget {
  final Color color;
  const _PulseDot({required this.color});

  @override
  State<_PulseDot> createState() => _PulseDotState();
}

class _PulseDotState extends State<_PulseDot>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctl = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1400),
  )..repeat(reverse: true);

  @override
  void dispose() {
    _ctl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _ctl,
      builder: (_, __) => Container(
        width: 8,
        height: 8,
        decoration: BoxDecoration(
          color: widget.color.withValues(alpha: 0.6 + _ctl.value * 0.4),
          shape: BoxShape.circle,
          boxShadow: [
            BoxShadow(
              color: widget.color.withValues(alpha: 0.4 + _ctl.value * 0.4),
              blurRadius: 6 + _ctl.value * 6,
              spreadRadius: -1,
            ),
          ],
        ),
      ),
    );
  }
}
