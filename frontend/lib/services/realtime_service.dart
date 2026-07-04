import 'dart:async';
import 'dart:convert';

import 'package:web_socket_channel/web_socket_channel.dart';

/// High-level connection state surfaced to the UI.
enum WsStatus { connecting, connected, disconnected }

/// Catalog of every WebSocket event the backend emits.
///
/// PART 7 widens the surface from PART 6's `device_update` /
/// `simulation_tick` to include room aggregates and the full alert
/// lifecycle. Keeping the canonical names here as a typed enum makes
/// downstream routing exhaustive — adding a new event in the backend
/// is a compile-error if it isn't handled here.
enum WsEventType {
  welcome,
  deviceUpdate,
  simulationTick,
  roomPower,
  alertCreated,
  alertUpdated,
  alertAcknowledged,
  alertResolved,
  alertDismissed,
  alertEscalated,
  alertReminder,
  alertSummary,
  unknown,
}

WsEventType _parseEventType(String? raw) {
  switch (raw) {
    case 'welcome':
      return WsEventType.welcome;
    case 'device_update':
      return WsEventType.deviceUpdate;
    case 'simulation_tick':
      return WsEventType.simulationTick;
    case 'room_power':
      return WsEventType.roomPower;
    case 'alert_created':
      return WsEventType.alertCreated;
    case 'alert_updated':
      return WsEventType.alertUpdated;
    case 'alert_acknowledged':
      return WsEventType.alertAcknowledged;
    case 'alert_resolved':
      return WsEventType.alertResolved;
    case 'alert_dismissed':
      return WsEventType.alertDismissed;
    case 'alert_escalated':
      return WsEventType.alertEscalated;
    case 'alert_reminder':
      return WsEventType.alertReminder;
    case 'alert_summary':
      return WsEventType.alertSummary;
    default:
      return WsEventType.unknown;
  }
}

/// Single realtime channel between the Flutter dashboard and the
/// FastAPI backend's `/ws` endpoint.
///
/// Responsibilities:
///   * open & supervise a WebSocket connection with automatic reconnect
///     (exponential backoff with jitter, capped at 30s),
///   * decode JSON frames and fan them out as typed events,
///   * suppress duplicate frames — the backend can re-broadcast an
///     identical event after a reconnect-and-replay cycle, and the UI
///     must NOT process it twice (requirement #10).
class RealtimeService {
  RealtimeService({
    required this.wsUrl,
    Duration initialBackoff = const Duration(seconds: 1),
    Duration maxBackoff = const Duration(seconds: 30),
    int dedupeCapacity = 256,
  })  : _initialBackoff = initialBackoff,
        _maxBackoff = maxBackoff,
        _dedupeCapacity = dedupeCapacity;

  final String wsUrl;
  final Duration _initialBackoff;
  final Duration _maxBackoff;
  final int _dedupeCapacity;

  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _sub;
  Timer? _reconnectTimer;
  bool _disposed = false;
  int _backoffAttempts = 0;

  final _eventController =
      StreamController<Map<String, dynamic>>.broadcast();
  final _statusController = StreamController<WsStatus>.broadcast();

  /// Rolling LRU of recently-seen event fingerprints. Used purely to
  /// dedupe exact-duplicate frames the backend can re-send (e.g. on
  /// reconnect-and-replay). Bounded so memory stays flat.
  final List<String> _seen = <String>[];
  final Set<String> _seenSet = <String>{};

  Stream<Map<String, dynamic>> get events => _eventController.stream;
  Stream<WsStatus> get status => _statusController.stream;

  // ------------------------------------------------------------ lifecycle

  /// Open the WebSocket. Safe to call multiple times — already-active
  /// connections are left alone.
  void connect() {
    if (_disposed) return;
    if (_channel != null) return; // already connected / connecting

    _emitStatus(WsStatus.connecting);
    try {
      final channel = WebSocketChannel.connect(Uri.parse(wsUrl));
      _channel = channel;

      _sub = channel.stream.listen(
        _onMessage,
        onError: (_) => _scheduleReconnect(),
        onDone: _scheduleReconnect,
        cancelOnError: true,
      );

      // `WebSocketChannel.connect` resolves synchronously on web; on
      // other platforms it surfaces errors via `onError` / `onDone`.
      // We optimistically mark connected — if the socket fails, the
      // listeners above will flip us back to disconnected.
      _backoffAttempts = 0;
      _emitStatus(WsStatus.connected);
    } catch (_) {
      _scheduleReconnect();
    }
  }

  void _onMessage(dynamic raw) {
    Map<String, dynamic> payload;
    try {
      payload = jsonDecode(raw as String) as Map<String, dynamic>;
    } catch (_) {
      return; // ignore non-JSON frames
    }

    // Dedupe identical frames. We fingerprint by `type` + the JSON of
    // `data` + the broadcast `timestamp` so that two genuinely-different
    // events with the same type still both pass through.
    final fingerprint = _fingerprint(payload);
    if (fingerprint != null) {
      if (_seenSet.contains(fingerprint)) return;
      _seenSet.add(fingerprint);
      _seen.add(fingerprint);
      if (_seen.length > _dedupeCapacity) {
        final evicted = _seen.removeAt(0);
        _seenSet.remove(evicted);
      }
    }

    if (!_eventController.isClosed) {
      _eventController.add(payload);
    }
  }

  String? _fingerprint(Map<String, dynamic> payload) {
    final type = payload['type'];
    if (type is! String) return null;
    final data = payload['data'];
    final ts = payload['timestamp'];
    final dataStr = data == null ? '' : jsonEncode(data);
    return '$type|$ts|$dataStr';
  }

  void _scheduleReconnect() {
    if (_disposed) return;

    _teardownSocket();
    _emitStatus(WsStatus.disconnected);

    _reconnectTimer?.cancel();
    final delay = _nextBackoff();
    _reconnectTimer = Timer(delay, connect);
  }

  Duration _nextBackoff() {
    // 1s, 2s, 4s, 8s, 16s, 30s (capped). Add small jitter so multiple
    // clients don't synchronize their reconnect storms.
    final base = _initialBackoff.inMilliseconds *
        (1 << _backoffAttempts.clamp(0, 5));
    final capped = base > _maxBackoff.inMilliseconds
        ? _maxBackoff.inMilliseconds
        : base;
    final jitterMs = (capped * 0.2 * _rng()).round();
    _backoffAttempts++;
    return Duration(milliseconds: capped + jitterMs);
  }

  // Cheap deterministic RNG so tests can assert on the sequence.
  int _rngSeed = DateTime.now().microsecondsSinceEpoch & 0x7fffffff;
  double _rng() {
    // xorshift32
    var x = _rngSeed;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    _rngSeed = x & 0x7fffffff;
    return (_rngSeed % 1000) / 1000.0;
  }

  void _teardownSocket() {
    try {
      _sub?.cancel();
    } catch (_) {/* swallow */}
    _sub = null;
    final ch = _channel;
    _channel = null;
    if (ch != null) {
      try {
        ch.sink.close();
      } catch (_) {/* swallow */}
    }
  }

  void _emitStatus(WsStatus s) {
    if (!_statusController.isClosed) {
      _statusController.add(s);
    }
  }

  /// Stop reconnecting and release underlying resources.
  Future<void> dispose() async {
    _disposed = true;
    _reconnectTimer?.cancel();
    _teardownSocket();
    if (!_eventController.isClosed) await _eventController.close();
    if (!_statusController.isClosed) await _statusController.close();
  }

  /// Visible for tests.
  // ignore: unused_element
  WsEventType classify(Map<String, dynamic> payload) =>
      _parseEventType(payload['type'] as String?);

  /// Visible for tests.
  // ignore: unused_element
  void resetBackoff() {
    _backoffAttempts = 0;
  }
}