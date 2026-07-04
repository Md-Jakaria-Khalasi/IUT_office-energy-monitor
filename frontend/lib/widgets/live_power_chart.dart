import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import 'glass_card.dart';

/// Line chart of recent total-power samples drawn entirely with
/// [CustomPainter] — no extra deps. Filled under the curve + glowing
/// gradient line.
class LivePowerChart extends StatefulWidget {
  final Stream<double> samples;
  final int maxPoints;
  final double currentPower;

  const LivePowerChart({
    super.key,
    required this.samples,
    required this.currentPower,
    this.maxPoints = 60,
  });

  @override
  State<LivePowerChart> createState() => _LivePowerChartState();
}

class _LivePowerChartState extends State<LivePowerChart> {
  final List<double> _points = [];
  StreamSubscription<double>? _sub;

  @override
  void initState() {
    super.initState();
    _sub = widget.samples.listen((s) {
      setState(() {
        _points.add(s);
        if (_points.length > widget.maxPoints) {
          _points.removeAt(0);
        }
      });
    });
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final series = List<double>.from(_points);
    return GlassCard(
      padding: const EdgeInsets.all(AppSpacing.xxl),
      shadows: AppGlow.soft(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('LIVE POWER', style: AppText.sectionTitle(context)),
              const SizedBox(width: 8),
              Container(
                width: 8,
                height: 8,
                decoration: const BoxDecoration(
                  color: AppColors.primary,
                  shape: BoxShape.circle,
                ),
              ),
              const Spacer(),
              Text(
                '${widget.currentPower.toStringAsFixed(0)} W now',
                style: AppText.body(context).copyWith(color: AppColors.primary),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.lg),
          SizedBox(
            height: 220,
            child: series.length < 2
                ? Center(
                    child: Text(
                      'Awaiting samples…',
                      style: AppText.bodyMuted(context),
                    ),
                  )
                : CustomPaint(
                    size: Size.infinite,
                    painter: _LinePainter(series),
                  ),
          ),
        ],
      ),
    );
  }
}

class _LinePainter extends CustomPainter {
  final List<double> series;
  _LinePainter(this.series);

  @override
  void paint(Canvas canvas, Size size) {
    if (series.length < 2) return;
    final maxV = (series.reduce(math.max)) * 1.15 + 1;
    const minV = 0.0;

    final gridPaint = Paint()
      ..color = AppColors.border.withValues(alpha: 0.6)
      ..strokeWidth = 1
      ..style = PaintingStyle.stroke;
    for (var i = 0; i < 4; i++) {
      final y = size.height * (i / 3);
      canvas.drawLine(Offset(0, y), Offset(size.width, y), gridPaint);
    }

    final pts = <Offset>[];
    final dx = size.width / (series.length - 1);
    for (var i = 0; i < series.length; i++) {
      final norm = (series[i] - minV) / (maxV - minV);
      final y = size.height - norm * size.height;
      pts.add(Offset(i * dx, y));
    }

    final path = Path()..moveTo(pts.first.dx, pts.first.dy);
    for (var i = 1; i < pts.length; i++) {
      final p = pts[i];
      final pp = pts[i - 1];
      final cp = Offset((pp.dx + p.dx) / 2, (pp.dy + p.dy) / 2);
      path.quadraticBezierTo(pp.dx, pp.dy, cp.dx, cp.dy);
    }
    path.lineTo(pts.last.dx, pts.last.dy);

    final glowPaint = Paint()
      ..color = AppColors.primary.withValues(alpha: 0.5)
      ..strokeWidth = 4
      ..style = PaintingStyle.stroke
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 6);
    canvas.drawPath(path, glowPaint);

    final linePaint = Paint()
      ..shader = const LinearGradient(
        colors: [AppColors.primary, AppColors.accentTeal],
        begin: Alignment.centerLeft,
        end: Alignment.centerRight,
      ).createShader(Rect.fromLTWH(0, 0, size.width, size.height))
      ..strokeWidth = 2.4
      ..style = PaintingStyle.stroke
      ..strokeJoin = StrokeJoin.round
      ..strokeCap = StrokeCap.round;
    canvas.drawPath(path, linePaint);

    final fillPath = Path.from(path)
      ..lineTo(size.width, size.height)
      ..lineTo(0, size.height)
      ..close();
    final fillPaint = Paint()
      ..shader = LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [
          AppColors.primary.withValues(alpha: 0.30),
          AppColors.primary.withValues(alpha: 0.02),
        ],
      ).createShader(Rect.fromLTWH(0, 0, size.width, size.height));
    canvas.drawPath(fillPath, fillPaint);

    final dot = Paint()
      ..color = AppColors.primary
      ..style = PaintingStyle.fill;
    canvas.drawCircle(pts.last, 4.5, dot);
    canvas.drawCircle(
      pts.last,
      9,
      Paint()
        ..color = AppColors.primary.withValues(alpha: 0.3)
        ..style = PaintingStyle.fill,
    );
  }

  @override
  bool shouldRepaint(covariant _LinePainter old) => old.series != series;
}