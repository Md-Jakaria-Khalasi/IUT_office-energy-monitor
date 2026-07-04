import 'package:flutter/material.dart';

import '../config.dart';
import '../models/device.dart';
import '../services/api_service.dart';
import '../services/dashboard_state.dart';
import '../services/realtime_service.dart';
import '../theme/app_theme.dart';
import '../widgets/active_alerts_card.dart';
import '../widgets/header_card.dart';
import '../widgets/live_power_chart.dart';
import '../widgets/power_by_room_doughnut.dart';
import '../widgets/room_card.dart';
import '../widgets/status_bar.dart';
import '../widgets/system_overview_card.dart';

/// Top-level dashboard screen. Composes the redesigned layout:
///
///   ┌──────────────────────────────────────────────────────┐
///   │  HeaderCard (title + 5 stat tiles + LIVE + clock)    │
///   ├──────────────────────────────────────────────────────┤
///   │  StatusBar (WS · API · Updates · simulation)         │
///   ├──────────────┬─────────────────┬─────────────────────┤
///   │  Rooms grid  │  LivePowerChart │  ActiveAlertsCard   │
///   │  (3 cards)   │  PowerByRoom    │  SystemOverviewCard │
///   │              │  Doughnut       │                     │
///   └──────────────┴─────────────────┴─────────────────────┘
///
/// Responsive:
///   - wide  (>= 1280): 3-column grid
///   - mid   (>= 980):  2-column grid (rooms + right rail side-by-side,
///                       charts column drops below)
///   - narrow (< 980):  single column, all sections stacked.
class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  late final ApiService _api = ApiService(baseUrl: BASE_URL);
  late final RealtimeService _realtime = RealtimeService(wsUrl: WS_URL);
  late final DashboardState _state = DashboardState(
    api: _api,
    realtime: _realtime,
  );

  bool _officeOpen({DateTime? t}) {
    final now = t ?? DateTime.now();
    final isWeekend = now.weekday == DateTime.saturday ||
        now.weekday == DateTime.sunday;
    if (isWeekend) return false;
    final h = now.hour;
    return h >= 9 && h < 18;
  }

  @override
  void initState() {
    super.initState();
    _state.start();
  }

  @override
  void dispose() {
    _realtime.dispose();
    _state.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: ListenableBuilder(
          listenable: _state,
          builder: (context, _) {
            final s = _state;
            if (s.initialLoading && s.overview == null) {
              return _LoadingScaffold(state: s);
            }
            if (s.errorMessage != null && s.overview == null) {
              return _ErrorScaffold(
                state: s,
                message: s.errorMessage!,
              );
            }
            return _DashboardBody(
              state: s,
              officeOpen: _officeOpen(),
            );
          },
        ),
      ),
    );
  }
}

class _DashboardBody extends StatelessWidget {
  final DashboardState state;
  final bool officeOpen;
  const _DashboardBody({required this.state, required this.officeOpen});

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.maxWidth;
        // Account for horizontal padding (xxl on each side = 48 each side = 96)
        // to compute breakpoints more realistically.
        final inner = width - 96;
        final isWide = inner >= 1180;
        final isMid = inner >= 760 && inner < 1180;
        final horizontalPad =
            width < 700 ? AppSpacing.lg : AppSpacing.xxxl;

        return SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          padding: EdgeInsets.fromLTRB(
            horizontalPad,
            AppSpacing.xxl,
            horizontalPad,
            AppSpacing.xxxl,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              HeaderCard(
                overview: state.overview,
                now: DateTime.now(),
              ),
              const SizedBox(height: AppSpacing.xl),
              StatusBar(
                wsStatus: state.connection,
                lastUpdate: state.lastUpdate,
              ),
              const SizedBox(height: AppSpacing.xxl),
              if (isWide)
                _ThreeColumnLayout(state: state, officeOpen: officeOpen)
              else if (isMid)
                _TwoColumnLayout(state: state, officeOpen: officeOpen)
              else
                _StackedLayout(state: state, officeOpen: officeOpen),
            ],
          ),
        );
      },
    );
  }
}

/// 3-column desktop layout.
class _ThreeColumnLayout extends StatelessWidget {
  final DashboardState state;
  final bool officeOpen;
  const _ThreeColumnLayout({required this.state, required this.officeOpen});

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          flex: 5,
          child: _RoomsColumn(state: state),
        ),
        const SizedBox(width: AppSpacing.xl),
        Expanded(
          flex: 4,
          child: _ChartsColumn(state: state),
        ),
        const SizedBox(width: AppSpacing.xl),
        Expanded(
          flex: 3,
          child: _RightRail(state: state, officeOpen: officeOpen),
        ),
      ],
    );
  }
}

/// 2-column tablet layout: rooms + right rail side-by-side, charts drop below.
class _TwoColumnLayout extends StatelessWidget {
  final DashboardState state;
  final bool officeOpen;
  const _TwoColumnLayout({required this.state, required this.officeOpen});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              flex: 6,
              child: _RoomsColumn(state: state),
            ),
            const SizedBox(width: AppSpacing.xl),
            Expanded(
              flex: 5,
              child: _RightRail(state: state, officeOpen: officeOpen),
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.xl),
        _ChartsColumn(state: state),
      ],
    );
  }
}

/// 1-column mobile layout.
class _StackedLayout extends StatelessWidget {
  final DashboardState state;
  final bool officeOpen;
  const _StackedLayout({required this.state, required this.officeOpen});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _RoomsColumn(state: state),
        const SizedBox(height: AppSpacing.xl),
        _ChartsColumn(state: state),
        const SizedBox(height: AppSpacing.xl),
        ActiveAlertsCard(alerts: state.alerts),
        const SizedBox(height: AppSpacing.xl),
        SystemOverviewCard(
          connection: state.connection,
          lastUpdate: state.lastUpdate,
          officeOpen: officeOpen,
        ),
      ],
    );
  }
}

class _RoomsColumn extends StatelessWidget {
  final DashboardState state;
  const _RoomsColumn({required this.state});

  @override
  Widget build(BuildContext context) {
    final rooms = state.rooms;
    if (rooms.isEmpty) {
      return const _RoomsEmpty();
    }
    return LayoutBuilder(
      builder: (context, constraints) {
        final w = constraints.maxWidth;
        // Responsive: 3 columns on wide, 2 on medium, 1 on narrow.
        // Each card needs a floor of ~280px; beyond that we add columns.
        int columns;
        if (w >= 920) {
          columns = 3;
        } else if (w >= 600) {
          columns = 2;
        } else {
          columns = 1;
        }
        final spacing = AppSpacing.xl;
        final cardWidth =
            (w - spacing * (columns - 1)) / columns;
        return Wrap(
          spacing: spacing,
          runSpacing: spacing,
          children: [
            for (final r in rooms)
              SizedBox(
                width: cardWidth,
                child: RoomCard(
                  room: r,
                  devices: _devicesForRoom(r.room),
                  onToggleDevice: state.toggleDevice,
                  onSetRoom: (s) => state.setRoomStatus(r.room, s),
                ),
              ),
          ],
        );
      },
    );
  }

  List<Device> _devicesForRoom(String room) =>
      state.devices.where((d) => d.room == room).toList();
}

class _RoomsEmpty extends StatelessWidget {
  const _RoomsEmpty();
  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.xxl),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppRadius.card),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.meeting_room_outlined,
              color: AppColors.secondary, size: 36),
          const SizedBox(height: AppSpacing.md),
          Text('No rooms reporting yet',
              style: AppText.title(context)),
          const SizedBox(height: AppSpacing.sm),
          Text(
            'Waiting for the first telemetry tick from the backend.',
            textAlign: TextAlign.center,
            style: AppText.bodyMuted(context),
          ),
        ],
      ),
    );
  }
}

class _ChartsColumn extends StatelessWidget {
  final DashboardState state;
  const _ChartsColumn({required this.state});

  @override
  Widget build(BuildContext context) {
    final chart = LivePowerChart(
      samples: state.samples,
      currentPower: state.totalPower,
      maxPoints: 60,
    );
    final doughnut = PowerByRoomDoughnut(
      rooms: state.rooms,
      totalPower: state.totalPower,
    );
    return Column(
      children: [
        chart,
        const SizedBox(height: AppSpacing.xl),
        doughnut,
      ],
    );
  }
}

class _RightRail extends StatelessWidget {
  final DashboardState state;
  final bool officeOpen;
  const _RightRail({required this.state, required this.officeOpen});

  @override
  Widget build(BuildContext context) {
    // ActiveAlertsCard already constrains its scroll list internally
    // (ConstrainedBox(maxHeight: 340)) — we do NOT need to force an
    // Expanded here, because this widget sits inside an Expanded-in-Row
    // without IntrinsicHeight, so the parent height is unbounded.
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: [
        ActiveAlertsCard(alerts: state.alerts),
        const SizedBox(height: AppSpacing.xl),
        SystemOverviewCard(
          connection: state.connection,
          lastUpdate: state.lastUpdate,
          officeOpen: officeOpen,
        ),
      ],
    );
  }
}

class _LoadingScaffold extends StatelessWidget {
  final DashboardState state;
  const _LoadingScaffold({required this.state});
  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 64,
            height: 64,
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(AppRadius.card),
              border: Border.all(color: AppColors.border),
            ),
            alignment: Alignment.center,
            child: const SizedBox(
              width: 28,
              height: 28,
              child: CircularProgressIndicator(
                color: AppColors.primary,
                strokeWidth: 3,
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.lg),
          Text(
            'Connecting to office telemetry...',
            style: AppText.bodyMuted(context),
          ),
        ],
      ),
    );
  }
}

class _ErrorScaffold extends StatelessWidget {
  final DashboardState state;
  final String message;
  const _ErrorScaffold({required this.state, required this.message});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xxxl),
        child: Container(
          padding: const EdgeInsets.all(AppSpacing.xxl),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(AppRadius.card),
            border: Border.all(
              color: AppColors.danger.withValues(alpha: 0.4),
            ),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(
                Icons.cloud_off,
                color: AppColors.danger,
                size: 36,
              ),
              const SizedBox(height: AppSpacing.lg),
              Text(
                'Cannot reach backend',
                style: AppText.title(context),
              ),
              const SizedBox(height: AppSpacing.sm),
              Text(
                message,
                textAlign: TextAlign.center,
                style: AppText.bodyMuted(context),
              ),
              const SizedBox(height: AppSpacing.xl),
              _RetryButton(state: state),
            ],
          ),
        ),
      ),
    );
  }
}

class _RetryButton extends StatelessWidget {
  final DashboardState state;
  const _RetryButton({required this.state});
  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppColors.primary,
      borderRadius: BorderRadius.circular(AppRadius.pill),
      child: InkWell(
        onTap: () => state.refreshAll(),
        borderRadius: BorderRadius.circular(AppRadius.pill),
        child: const Padding(
          padding: EdgeInsets.symmetric(
            horizontal: AppSpacing.xl,
            vertical: AppSpacing.md,
          ),
          child: Text(
            'Retry',
            style: TextStyle(
              color: AppColors.background,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.5,
            ),
          ),
        ),
      ),
    );
  }
}