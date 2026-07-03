import 'package:flutter/material.dart';

import '../services/realtime_service.dart';
import '../theme/app_theme.dart';

class ConnectionIndicator extends StatelessWidget {
  final WsStatus status;
  const ConnectionIndicator({super.key, required this.status});

  @override
  Widget build(BuildContext context) {
    final color = switch (status) {
      WsStatus.connected => AppColors.success,
      WsStatus.connecting => AppColors.warning,
      WsStatus.disconnected => AppColors.danger,
    };
    final label = switch (status) {
      WsStatus.connected => 'Live',
      WsStatus.connecting => 'Connecting',
      WsStatus.disconnected => 'Offline',
    };
    return Semantics(
      label: 'Realtime connection status: $label',
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: color.withOpacity(0.12),
          borderRadius: BorderRadius.circular(999),
          border: Border.all(color: color.withOpacity(0.35)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            _Pulse(color: color, animate: status == WsStatus.connected),
            const SizedBox(width: 8),
            Text(
              label,
              style: Theme.of(context).textTheme.labelMedium?.copyWith(
                    color: color,
                    fontWeight: FontWeight.w600,
                  ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Pulse extends StatefulWidget {
  final Color color;
  final bool animate;
  const _Pulse({required this.color, required this.animate});

  @override
  State<_Pulse> createState() => _PulseState();
}

class _PulseState extends State<_Pulse>
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
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (_, __) {
        final scale = widget.animate ? 0.6 + (_ctrl.value * 0.6) : 1.0;
        return Container(
          width: 10 * scale,
          height: 10 * scale,
          decoration: BoxDecoration(
            color: widget.color,
            shape: BoxShape.circle,
          ),
        );
      },
    );
  }
}