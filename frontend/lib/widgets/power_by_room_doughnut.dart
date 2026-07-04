import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../models/device.dart';
import '../theme/app_theme.dart';
import 'glass_card.dart';

/// Doughnut showing how live power is split across rooms. Drawn with
/// [CustomPainter] to avoid pulling in `fl_chart`. The center shows the
/// total watts and a "WATTS" caption beneath it.
class PowerByRoomDoughnut extends StatelessWidget {
  final List<RoomSummary> rooms;
  final double totalPower;

  const PowerByRoomDoughnut({
    super.key,
    required this.rooms,
    required this.totalPower,
  });

  static final _palette = <Color>[
    AppColors.primary,
    AppColors.accentTeal,
    AppColors.secondary,
    AppColors.warning,
    AppColors.danger,
  ];

  @override
  Widget build(BuildContext context) {
    final entries = rooms.where((r) => r.totalPower > 0).toList();
    final hasData = entries.isNotEmpty;
    return GlassCard(
      padding: const EdgeInsets.all(AppSpacing.xxl),
      shadows: AppGlow.soft(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('POWER BY ROOM', style: AppText.sectionTitle(context)),
          const SizedBox(height: AppSpacing.lg),
          SizedBox(
            height: 180,
            child: hasData
                ? CustomPaint(
                    size: Size.infinite,
                    painter: _DoughnutPainter(entries, totalPower, _palette),
                  )
                : Center(
                    child: Text(
                      'No power data yet',
                      style: AppText.bodyMuted(context),
                    ),
                  ),
          ),
          const SizedBox(height: AppSpacing.lg),
          ...List.generate(entries.length, (i) {
            final e = entries[i];
            final pct = totalPower == 0
                ? 0.0
                : (e.totalPower / totalPower * 100);
            return Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                children: [
                  Container(
                    width: 10,
                    height: 10,
                    decoration: BoxDecoration(
                      color: _palette[i % _palette.length],
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(child: Text(e.room, style: AppText.body(context))),
                  Text(
                    '${e.totalPower.toStringAsFixed(0)} W  (${pct.toStringAsFixed(0)}%)',
                    style: AppText.bodyMuted(context).copyWith(fontSize: 12),
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }
}

class _DoughnutPainter extends CustomPainter {
  final List<RoomSummary> rooms;
  final double totalPower;
  final List<Color> palette;
  _DoughnutPainter(this.rooms, this.totalPower, this.palette);

  @override
  void paint(Canvas canvas, Size size) {
    final radius = math.min(size.width, size.height) / 2;
    final center = Offset(size.width / 2, size.height / 2);
    final rect = Rect.fromCircle(center: center, radius: radius - 6);
    final stroke = radius * 0.32;
    var start = -math.pi / 2;
    final total = totalPower == 0 ? 1.0 : totalPower;

    final bgPaint = Paint()
      ..color = AppColors.surfaceHigh
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke;
    canvas.drawCircle(center, radius - stroke / 2 - 4, bgPaint);

    for (var i = 0; i < rooms.length; i++) {
      final r = rooms[i];
      final sweep = (r.totalPower / total) * math.pi * 2;
      final color = palette[i % palette.length];
      final paint = Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = stroke
        ..strokeCap = StrokeCap.round;
      canvas.drawArc(rect, start, sweep - 0.02, false, paint);
      start += sweep;
    }

    final tp = TextPainter(
      text: TextSpan(
        text: totalPower.toStringAsFixed(0),
        style: const TextStyle(
          fontSize: 26,
          color: AppColors.textPrimary,
          fontWeight: FontWeight.w700,
          letterSpacing: -0.5,
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(
      canvas,
      Offset(center.dx - tp.width / 2, center.dy - tp.height / 2 - 8),
    );

    final label = TextPainter(
      text: const TextSpan(
        text: 'WATTS',
        style: TextStyle(
          color: AppColors.textMuted,
          fontSize: 10,
          letterSpacing: 1.4,
          fontWeight: FontWeight.w600,
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    label.paint(
      canvas,
      Offset(center.dx - label.width / 2, center.dy + 10),
    );
  }

  @override
  bool shouldRepaint(covariant _DoughnutPainter old) =>
      old.rooms != rooms || old.totalPower != totalPower;
}