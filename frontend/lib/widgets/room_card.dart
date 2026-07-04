import 'package:flutter/material.dart';

import '../models/device.dart';
import '../theme/app_theme.dart';
import 'device_row.dart';
import 'glass_card.dart';

/// Room summary card with ALL ON / ALL OFF controls and an inline list of
/// devices with realtime toggles.
class RoomCard extends StatelessWidget {
  final RoomSummary room;
  final List<Device> devices;
  final ValueChanged<Device> onToggleDevice;
  final ValueChanged<String> onSetRoom; // 'on' or 'off'
  final bool busy;

  const RoomCard({
    super.key,
    required this.room,
    required this.devices,
    required this.onToggleDevice,
    required this.onSetRoom,
    this.busy = false,
  });

  IconData get _icon => switch (room.room.toLowerCase()) {
        'drawing room' => Icons.brush_outlined,
        'work room 1' => Icons.work_outline,
        'work room 2' => Icons.work_outline,
        _ => Icons.meeting_room_outlined,
      };

  @override
  Widget build(BuildContext context) {
    final allOff = room.activeDevices == 0;
    final canAllOff = !allOff;

    return GlassCard(
      shadows: AppGlow.soft(),
      padding: const EdgeInsets.all(AppSpacing.xxl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(color: AppColors.primary.withValues(alpha: 0.45)),
                ),
                child: Icon(_icon, color: AppColors.primary, size: 24),
              ),
              const SizedBox(width: AppSpacing.lg),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(room.room, style: AppText.title(context)),
                    const SizedBox(height: 4),
                    Text(
                      '${room.activeDevices}/${room.totalDevices} ON',
                      style: AppText.bodyMuted(context).copyWith(fontSize: 12),
                    ),
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    room.totalPower.toStringAsFixed(0),
                    style: AppText.metric(context, size: 24).copyWith(
                      color: AppColors.primary,
                    ),
                  ),
                  Text('WATTS', style: AppText.caption(context)),
                ],
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.lg),
          Row(
            children: [
              Expanded(
                child: _RoomAction(
                  label: 'ALL ON',
                  icon: Icons.power_settings_new,
                  color: AppColors.success,
                  enabled: !busy && !allOff ? false : (room.activeDevices < room.totalDevices),
                  onTap: () => onSetRoom('on'),
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: _RoomAction(
                  label: 'ALL OFF',
                  icon: Icons.power_off,
                  color: AppColors.danger,
                  enabled: !busy && canAllOff,
                  onTap: () => onSetRoom('off'),
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.lg),
          if (devices.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
              child: Text(
                'No devices registered in this room yet.',
                style: AppText.bodyMuted(context),
                textAlign: TextAlign.center,
              ),
            )
          else
            ...devices.map((d) => Padding(
                  padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                  child: DeviceRow(
                    device: d,
                    onToggle: (_) => onToggleDevice(d),
                  ),
                )),
        ],
      ),
    );
  }
}

class _RoomAction extends StatelessWidget {
  final String label;
  final IconData icon;
  final Color color;
  final bool enabled;
  final VoidCallback onTap;

  const _RoomAction({
    required this.label,
    required this.icon,
    required this.color,
    required this.enabled,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Opacity(
      opacity: enabled ? 1 : 0.45,
      child: GestureDetector(
        onTap: enabled ? onTap : null,
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 10),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.1),
            border: Border.all(color: color.withValues(alpha: 0.5)),
            borderRadius: BorderRadius.circular(AppRadius.inner),
            boxShadow: enabled
                ? [BoxShadow(color: color.withValues(alpha: 0.25), blurRadius: 14, spreadRadius: -2)]
                : null,
          ),
          alignment: Alignment.center,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, size: 16, color: color),
              const SizedBox(width: 6),
              Text(
                label,
                style: AppText.caption(context).copyWith(color: color, fontSize: 12),
              ),
            ],
          ),
        ),
      ),
    );
  }
}