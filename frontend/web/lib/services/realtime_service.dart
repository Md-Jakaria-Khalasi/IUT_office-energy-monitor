import 'dart:async';
import 'dart:convert';

import 'package:web_socket_channel/web_socket_channel.dart';

enum WsStatus { connecting, connected, disconnected }

class RealtimeService {
  final String wsUrl;
  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _sub;
  Timer? _reconnectTimer;

  final _eventController = StreamController<Map<String, dynamic>>.broadcast();
  final _statusController = StreamController<WsStatus>.broadcast();

  RealtimeService({required this.wsUrl});

  Stream<Map<String, dynamic>> get events => _eventController.stream;
  Stream<WsStatus> get status => _statusController.stream;

  void connect() {
    _statusController.add(WsStatus.connecting);
    try {
      _channel = WebSocketChannel.connect(Uri.parse(wsUrl));
      _statusController.add(WsStatus.connected);
      _sub = _channel!.stream.listen(
        (raw) {
          try {
            final payload = jsonDecode(raw as String) as Map<String, dynamic>;
            _eventController.add(payload);
          } catch (_) {
            // ignore non-JSON payloads
          }
        },
        onError: (_) => _scheduleReconnect(),
        onDone: _scheduleReconnect,
        cancelOnError: true,
      );
    } catch (_) {
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    _statusController.add(WsStatus.disconnected);
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(const Duration(seconds: 3), connect);
  }

  Future<void> dispose() async {
    _reconnectTimer?.cancel();
    await _sub?.cancel();
    await _channel?.sink.close();
    await _eventController.close();
    await _statusController.close();
  }
}