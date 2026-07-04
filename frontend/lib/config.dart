/// Frontend configuration. Single source of truth for backend endpoints.
///
/// Both [BASE_URL] and [WS_URL] can be overridden at build time via
/// `--dart-define`, e.g.:
///
///   flutter run -d chrome \
///     --dart-define=API_BASE_URL=https://api.example.com \
///     --dart-define=WS_URL=wss://api.example.com/ws
///
/// When the `API_BASE_URL` override is provided but `WS_URL` is not, the
/// WebSocket URL is derived by swapping the scheme (`http` → `ws`,
/// `https` → `wss`) and appending `/ws`. The opposite also works: if
/// only `WS_URL` is provided, the REST base URL is derived from it.
library;

// ignore_for_file: non_constant_identifier_names
// The public names BASE_URL / WS_URL are intentionally
// SCREAMING_SNAKE_CASE so the rest of the codebase (and call-sites
// in widgets) reads naturally as `BASE_URL` regardless of where
// the value comes from.

/// Default REST endpoint. Matches the local FastAPI process during
/// development.
const String _kDefaultBaseUrl = 'http://127.0.0.1:8001';

/// Default WebSocket endpoint. Matches the local FastAPI process
/// during development.
const String _kDefaultWsUrl = 'ws://127.0.0.1:8001/ws';

const String _kApiDefine = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: _kDefaultBaseUrl,
);

const String _kWsDefine = String.fromEnvironment(
  'WS_URL',
  defaultValue: _kDefaultWsUrl,
);

/// Base URL of the REST API. Override at build time with
/// `--dart-define=API_BASE_URL=https://...`.
String get BASE_URL => _kApiDefine;

/// WebSocket endpoint of the live-updates channel. Override at build
/// time with `--dart-define=WS_URL=wss://...`.
String get WS_URL => _kWsDefine;