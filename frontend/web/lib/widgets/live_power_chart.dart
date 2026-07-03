import 'dart:async';
import 'dart:collection';

import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Lightweight sparkline that auto-scrolls with new power readings.
class LivePowerChart extends StatefulWidget {
  final Stream<double> samples;
  final int maxSamples;
  const LivePowerChart({super.key, required this.samples, this.maxSamples = 30});

  @override
  State<LivePowerChart> createState() => _LivePowerChartState();
}

class _LivePowerChartState extends State<LivePowerChart> {
  final Queue<double> _buffer = Queue<double>();
  StreamSubscription<double>? _sub;

  @override
  void initState() {
    super.initState();
    _sub = widget.samples.listen((sample) {
      setState(() {
        _buffer.addLast(sample);
        while (_buffer.length > widget.maxSamples) {
          _buffer.removeFirst();
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
    final values = _buffer.toList();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.flash_on, color: AppColors.primary),
                const SizedBox(width: 8),
                Text(
                  'Live Power Draw',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ],
            ),
            const SizedBox(height: 12),
            SizedBox(
              height: 120,
              child: values.isEmpty
                  ? const Center(
                      child: Text(
                        'Awaiting samples…',
                        style: TextStyle(color: AppColors.textSecondary),
                      ),
                    )
                  : CustomPaint(
                      size: Size.infinite,
                      painter: _SparklinePainter(values),
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SparklinePainter extends CustomPainter {
  final List<double> values;
  _SparklinePainter(this.values);

  @override
  void paint(Canvas canvas, Size size) {
    if (values.isEmpty) return;
    final maxV = values.reduce((a, b) => a > b ? a : b);
    final minV = values.reduce((a, b) => a < b ? a : b);
    final range = (maxV - minV).abs() < 0.0001 ? 1.0 : (maxV - minV);

    final paint = Paint()
      ..color = AppColors.primary
      ..strokeWidth = 2.5
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    final fill = Paint()
      ..shader = LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [
          AppColors.primary.withOpacity(0.4),
          AppColors.primary.withOpacity(0.0),
        ],
      ).createShader(Rect.fromLTWH(0, 0, size.width, size.height));

    final path = Path();
    final fillPath = Path();
    for (var i = 0; i < values.length; i++) {
      final x = i / (values.length - 1).clamp(1, double.infinity) * size.width;
      final y = size.height - ((values[i] - minV) / range) * size.height;
      if (i == 0) {
        path.moveTo(x, y);
        fillPath.moveTo(x, size.height);
        fillPath.lineTo(x, y);
      } else {
        path.lineTo(x, y);
        fillPath.lineTo(x, y);
      }
    }
    fillPath.lineTo(size.width, size.height);
    fillPath.close();
    canvas.drawPath(fillPath, fill);
    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant _SparklinePainter old) =>
      old.values.length != values.length || old.values.last != values.last;
}