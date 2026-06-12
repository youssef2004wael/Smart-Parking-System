import 'dart:async';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:provider/provider.dart';
import '../services/navigation_service.dart';
import '../providers/locale_provider.dart';
import '../providers/parking_provider.dart';
import '../utils/app_strings.dart';

class NavigationPage extends StatefulWidget {
  final String slotId;
  final String licensePlate;

  const NavigationPage({
    super.key,
    required this.slotId,
    required this.licensePlate,
  });

  @override
  State<NavigationPage> createState() => _NavigationPageState();
}

class _NavigationPageState extends State<NavigationPage>
    with TickerProviderStateMixin {
  final NavigationService _service = NavigationService();

  NavigationData? _navData;
  bool _isLoading = true;
  String? _error;

  CarLocation? _carLocation;
  Timer? _trackingTimer;
  Timer? _carAnimationTimer;
  bool _hasArrived = false;
  bool _isTracking = false;

  late AnimationController _pulseController;

  Set<String> _pathCellKeys = {};
  Map<String, int> _pathCellIndex = {};
  int _currentAnimIdx = 0;

  int get _minVisibleRow => 0;
  int get _maxVisibleRow {
    if (_navData == null) return 10;
    final destRow = _navData!.destination.row;
    final pathMaxRow = _navData!.path.fold<int>(0, (m, p) => max(m, p.row));
    return min(max(destRow + 3, pathMaxRow + 2), 51);
  }

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
    )..repeat(reverse: true);
    _loadNavigation();
  }

  @override
  void dispose() {
    _trackingTimer?.cancel();
    _carAnimationTimer?.cancel();
    _pulseController.dispose();
    super.dispose();
  }

  Future<void> _loadNavigation() async {
    try {
      setState(() { _isLoading = true; _error = null; });
      final rawData = await _service.fetchNavigation(widget.slotId);
      final data = NavigationData(
        slotNumber: rawData.slotNumber,
        entrance: Position(row: rawData.entrance.row, col: 5 - rawData.entrance.col),
        roadStop: Position(row: rawData.roadStop.row, col: 5 - rawData.roadStop.col),
        destination: Position(row: rawData.destination.row, col: 5 - rawData.destination.col),
        totalSteps: rawData.totalSteps,
        path: rawData.path.map((p) => Position(row: p.row, col: 5 - p.col)).toList(),
      );
      final keys = <String>{};
      final indexMap = <String, int>{};
      for (int i = 0; i < data.path.length; i++) {
        final p = data.path[i];
        keys.add('${p.row},${p.col}');
        indexMap['${p.row},${p.col}'] = i;
      }
      setState(() {
        _navData = data;
        _pathCellKeys = keys;
        _pathCellIndex = indexMap;
        _currentAnimIdx = 0;
        _isLoading = false;
      });
      _startTracking();
    } catch (e) {
      setState(() { _error = e.toString(); _isLoading = false; });
    }
  }

  void _startTracking() {
    if (widget.licensePlate.isEmpty) return;
    _isTracking = true;
    _fetchCarLocation();
    _trackingTimer = Timer.periodic(const Duration(seconds: 3), (_) => _fetchCarLocation());
  }

  Future<void> _fetchCarLocation() async {
    if (!mounted || _hasArrived) return;
    final rawLocation = await _service.fetchCarLocation(widget.licensePlate);
    if (!mounted) return;
    if (rawLocation != null) {
      final location = CarLocation(
        licensePlate: rawLocation.licensePlate,
        row: rawLocation.row,
        col: 5 - rawLocation.col,
        zone: rawLocation.zone,
        lastSeen: rawLocation.lastSeen,
      );
      setState(() { _carLocation = location; });
      
      final targetIdx = _getCarPathIndex();
      _animateCarToIndex(targetIdx, onComplete: () {
        if (!mounted) return;
        // 🚀 Fix: If the animation reached the final step of the path, we have arrived!
        if (_currentAnimIdx >= _navData!.path.length - 1) {
          _onArrived();
        } else {
          _checkArrival(location);
        }
      });
    }
  }

  void _animateCarToIndex(int targetIdx, {VoidCallback? onComplete}) {
    if (_navData == null) return;
    if (targetIdx <= _currentAnimIdx) {
      onComplete?.call();
      return;
    }

    _carAnimationTimer?.cancel();
    _carAnimationTimer = Timer.periodic(const Duration(milliseconds: 200), (timer) {
      if (!mounted) { timer.cancel(); return; }
      if (_currentAnimIdx < targetIdx) {
        setState(() { _currentAnimIdx++; });
      } else {
        timer.cancel();
        onComplete?.call();
      }
    });
  }

  void _checkArrival(CarLocation location) {
    if (_navData == null || _hasArrived) return;
    final dest = _navData!.destination;
    final rowDiff = (location.row - dest.row).abs();
    final colDiff = (location.col - dest.col).abs();
    if (rowDiff <= 1 && colDiff <= 1) _onArrived();
  }

  void _onArrived() {
    if (_hasArrived) return;
    setState(() => _hasArrived = true);
    _trackingTimer?.cancel();
    _carAnimationTimer?.cancel();

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) {
        final theme = Theme.of(ctx);
        return AlertDialog(
          backgroundColor: theme.cardColor,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(color: const Color(0xFF14C8A1).withOpacity(0.15), shape: BoxShape.circle),
                child: const Icon(Icons.check_circle, color: Color(0xFF14C8A1), size: 56),
              ),
              const SizedBox(height: 20),
              Text('You Have Arrived!', style: theme.textTheme.headlineMedium),
              const SizedBox(height: 12),
              Text('Park your car at slot ${widget.slotId}', textAlign: TextAlign.center, style: theme.textTheme.bodyMedium),
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 10),
                decoration: BoxDecoration(color: const Color(0xFF14C8A1).withOpacity(0.15), borderRadius: BorderRadius.circular(20)),
                child: Text(widget.slotId, style: const TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: Color(0xFF14C8A1))),
              ),
            ],
          ),
          actions: [
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () {
                  Navigator.pop(ctx);
                  context.read<ParkingProvider>().loadSlots();
                  context.read<ParkingProvider>().loadReservations();
                  Navigator.pop(context, true); // Return true to indicate arrival
                },
                child: const Text('Done', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
              ),
            ),
          ],
        );
      },
    );
  }

  String? _getSlotAt(int row, int col) {
    if (col == 0 && row >= 1 && row <= 45) return 'D$row';
    if (col == 2 && row >= 2 && row <= 17) return 'C${row - 1}';
    if (col == 3 && row >= 2 && row <= 17) return 'B${row - 1}';
    if (col == 5 && row >= 1 && row <= 50) return 'A$row';
    return null;
  }

  bool _isRoadCell(int row, int col) {
    if (row == 0 && col == 4) return true;
    if (row == 51 && col == 4) return true;
    if (col == 4 && row >= 1 && row <= 50) return true;
    if (col == 1 && row >= 1 && row <= 50) return true;
    if (row == 1 && (col == 2 || col == 3)) return true;
    if (row == 50 && (col == 2 || col == 3)) return true;
    return false;
  }

  bool _isOnPath(int row, int col) => _pathCellKeys.contains('$row,$col');

  bool _isCarAt(int row, int col) {
    if (_carLocation == null || _navData == null || _navData!.path.isEmpty || _currentAnimIdx >= _navData!.path.length) return false;
    final pos = _navData!.path[_currentAnimIdx];
    return pos.row == row && pos.col == col;
  }

  bool _isCarPassedPathCell(int row, int col) {
    final cellIdx = _pathCellIndex['$row,$col'];
    if (cellIdx == null) return false;
    return cellIdx < _currentAnimIdx;
  }

  int _getCarPathIndex() {
    if (_carLocation == null || _navData == null) return _currentAnimIdx;
    int bestIdx = _currentAnimIdx;
    double minDist = double.infinity;
    for (int i = _currentAnimIdx; i < _navData!.path.length; i++) {
      final p = _navData!.path[i];
      final dist = (p.row - _carLocation!.row).abs() + (p.col - _carLocation!.col).abs();
      if (dist < minDist) { minDist = dist.toDouble(); bestIdx = i; }
    }
    return bestIdx;
  }

  IconData? _getPathArrow(int row, int col) {
    final idx = _pathCellIndex['$row,$col'];
    if (idx == null || _navData == null) return null;
    if (idx < _navData!.path.length - 1) {
      final next = _navData!.path[idx + 1];
      final dr = next.row - row; final dc = next.col - col;
      if (dr > 0) return Icons.arrow_downward;
      if (dr < 0) return Icons.arrow_upward;
      if (dc > 0) return Icons.arrow_forward;
      if (dc < 0) return Icons.arrow_back;
    }
    return Icons.location_on;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final lang = context.watch<LocaleProvider>().locale.languageCode;
    return Scaffold(
      appBar: AppBar(
        title: Text('${AppStrings.get("navigateToSlot", lang)} ${widget.slotId}'),
        leading: IconButton(icon: const Icon(Icons.arrow_back), onPressed: () => Navigator.pop(context)),
        actions: [
          if (_isTracking) Padding(padding: const EdgeInsets.only(right: 8), child: AnimatedBuilder(animation: _pulseController, builder: (context, _) => Icon(Icons.videocam, color: _carLocation != null ? Color.lerp(Colors.green.shade800, Colors.green, _pulseController.value) : Colors.orange, size: 20))),
          IconButton(icon: const Icon(Icons.refresh), onPressed: _loadNavigation),
        ],
      ),
      body: _isLoading
          ? Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [CircularProgressIndicator(color: theme.colorScheme.primary), const SizedBox(height: 16), Text('Loading navigation...', style: theme.textTheme.bodyMedium)]))
          : _error != null
              ? Center(child: Padding(padding: const EdgeInsets.all(24), child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [const Icon(Icons.error_outline, color: Colors.red, size: 56), const SizedBox(height: 16), Text(_error!, style: theme.textTheme.bodyMedium, textAlign: TextAlign.center), const SizedBox(height: 24), ElevatedButton.icon(onPressed: _loadNavigation, icon: const Icon(Icons.refresh), label: const Text('Retry'))])))
              : _buildNavigationBody(theme, lang),
    );
  }

  Widget _buildNavigationBody(ThemeData theme, String lang) {
    return Column(children: [
      if (_isTracking) _buildTrackingBar(theme),
      _buildStepCounter(theme),
      _buildLegend(theme),
      const SizedBox(height: 4),
      Expanded(child: _buildGrid(theme)),
      _buildInfoBar(theme),
    ]);
  }

  Widget _buildStepCounter(ThemeData theme) {
    if (_navData == null) return const SizedBox();
    final totalSteps = _navData!.totalSteps;
    int remainingSteps = totalSteps - _currentAnimIdx;
    if (remainingSteps < 0) remainingSteps = 0;
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(gradient: LinearGradient(colors: [theme.colorScheme.primary.withOpacity(0.1), theme.colorScheme.secondary.withOpacity(0.1)]), borderRadius: BorderRadius.circular(12), border: Border.all(color: theme.dividerColor)),
      child: Row(children: [
        Icon(Icons.route, color: theme.colorScheme.primary, size: 24),
        const SizedBox(width: 12),
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(_hasArrived ? '✅ Arrived!' : _carLocation != null ? '$remainingSteps / $totalSteps steps remaining' : '$totalSteps steps to ${widget.slotId}', style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.bold)),
          const SizedBox(height: 4),
          ClipRRect(borderRadius: BorderRadius.circular(4), child: LinearProgressIndicator(value: (_currentAnimIdx / max(totalSteps, 1)).clamp(0.0, 1.0), backgroundColor: theme.dividerColor, valueColor: AlwaysStoppedAnimation<Color>(theme.colorScheme.primary), minHeight: 4)),
        ])),
        const SizedBox(width: 12),
        Container(padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6), decoration: BoxDecoration(color: theme.colorScheme.primary, borderRadius: BorderRadius.circular(20)), child: Text('$totalSteps', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16))),
      ]),
    );
  }

  Widget _buildGrid(ThemeData theme) {
    final isDark = theme.brightness == Brightness.dark;
    return SingleChildScrollView(padding: const EdgeInsets.symmetric(horizontal: 8), child: Column(children: [_buildColumnHeaders(theme), const SizedBox(height: 4), ...List.generate(_maxVisibleRow + 1, (row) => _buildGridRow(row, theme, isDark))]));
  }

  Widget _buildColumnHeaders(ThemeData theme) {
    const headers = ['D', 'Road', 'C', 'B', 'Road', 'A'];
    return Padding(padding: const EdgeInsets.symmetric(horizontal: 4), child: Row(children: [SizedBox(width: 28, child: Text('', style: theme.textTheme.bodySmall)), ...headers.map((h) => Expanded(child: Center(child: Text(h, style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: h == 'Road' ? Colors.orange.withOpacity(0.7) : theme.textTheme.bodySmall?.color)))))]));
  }

  Widget _buildGridRow(int row, ThemeData theme, bool isDark) {
    return Padding(padding: const EdgeInsets.symmetric(vertical: 1), child: Row(children: [SizedBox(width: 28, child: Text('$row', style: TextStyle(fontSize: 9, color: theme.textTheme.bodySmall?.color?.withOpacity(0.5)), textAlign: TextAlign.center)), ...List.generate(6, (col) => Expanded(child: _buildGridCell(row, col, theme, isDark)))]));
  }

  Widget _buildGridCell(int row, int col, ThemeData theme, bool isDark) {
    final isRoad = _isRoadCell(row, col); final slotName = _getSlotAt(row, col); final isPath = _isOnPath(row, col); final isCar = _isCarAt(row, col); final isDestSlot = slotName != null && slotName == widget.slotId; final isDestRoad = _navData != null && row == _navData!.roadStop.row && col == _navData!.roadStop.col; final isPassed = isPath && _isCarPassedPathCell(row, col); final arrow = isPath ? _getPathArrow(row, col) : null;
    bool isSlotAdjacentToPath = false;
    if (slotName != null && !isDestSlot) { for (final dc in [-1, 1]) { if (_pathCellKeys.contains('$row,${col + dc}')) { isSlotAdjacentToPath = true; break; } } }
    const double cellHeight = 28; Color bgColor; Color borderColor; Widget? content; List<BoxShadow>? shadows;
    if (row == 0 && col == 4) { bgColor = const Color(0xFF14C8A1).withOpacity(0.3); borderColor = const Color(0xFF14C8A1); content = const Icon(Icons.login, size: 12, color: Color(0xFF14C8A1)); }
    else if (row == 51 && col == 4) { bgColor = Colors.red.withOpacity(0.2); borderColor = Colors.red.withOpacity(0.5); content = const Icon(Icons.logout, size: 12, color: Colors.red); }
    else if (isCar && isRoad) { bgColor = const Color(0xFF2979FF); borderColor = const Color(0xFF1565C0); shadows = [BoxShadow(color: const Color(0xFF2979FF).withOpacity(0.5), blurRadius: 6, spreadRadius: 1)]; content = AnimatedBuilder(animation: _pulseController, builder: (_, __) => Icon(Icons.directions_car, color: Colors.white, size: 12 + _pulseController.value * 2)); }
    else if (isDestSlot) { bgColor = const Color(0xFF14C8A1); borderColor = const Color(0xFF0D7377); shadows = [BoxShadow(color: const Color(0xFF14C8A1).withOpacity(0.5), blurRadius: 8, spreadRadius: 1)]; content = Row(mainAxisAlignment: MainAxisAlignment.center, mainAxisSize: MainAxisSize.min, children: [const Icon(Icons.location_on, color: Colors.white, size: 10), Text(slotName!, style: const TextStyle(color: Colors.white, fontSize: 8, fontWeight: FontWeight.bold))]); }
    else if (isDestRoad && isPath) { bgColor = const Color(0xFFFFD600).withOpacity(0.6); borderColor = const Color(0xFFFFD600); content = Icon(arrow ?? Icons.arrow_forward, size: 14, color: const Color(0xFF14C8A1)); }
    else if (isPath && !isPassed && isRoad) { bgColor = const Color(0xFFFFD600).withOpacity(0.4); borderColor = const Color(0xFFFFD600).withOpacity(0.8); content = Icon(arrow ?? Icons.arrow_downward, size: 12, color: Colors.orange.shade800); }
    else if (isPassed && isRoad) { bgColor = isDark ? Colors.green.withOpacity(0.1) : Colors.green.withOpacity(0.08); borderColor = Colors.green.withOpacity(0.3); content = Icon(Icons.check, size: 10, color: Colors.green.withOpacity(0.5)); }
    else if (isRoad) { bgColor = isDark ? const Color(0xFF1A1F38).withOpacity(0.5) : const Color(0xFFF5F5F5); borderColor = isDark ? const Color(0xFF2A2F48).withOpacity(0.5) : Colors.grey.shade300; content = Icon(Icons.more_vert, size: 8, color: isDark ? Colors.white.withOpacity(0.1) : Colors.grey.withOpacity(0.3)); }
    else if (isSlotAdjacentToPath && slotName != null) { bgColor = isDark ? const Color(0xFF1A1F38) : Colors.white; borderColor = const Color(0xFFFFD600).withOpacity(0.3); content = Text(slotName, style: TextStyle(fontSize: 8, fontWeight: FontWeight.w500, color: isDark ? Colors.white70 : Colors.black54)); }
    else if (slotName != null) { bgColor = isDark ? const Color(0xFF1A1F38) : Colors.white; borderColor = isDark ? const Color(0xFF2A2F48) : Colors.grey.shade300; content = Text(slotName, style: TextStyle(fontSize: 8, color: isDark ? Colors.white38 : Colors.grey.shade400)); }
    else { bgColor = isDark ? const Color(0xFF0A0E21).withOpacity(0.3) : Colors.grey.shade100; borderColor = Colors.transparent; content = null; }
    return Container(height: cellHeight, margin: const EdgeInsets.all(1), decoration: BoxDecoration(color: bgColor, borderRadius: BorderRadius.circular(4), border: Border.all(color: borderColor, width: 0.5), boxShadow: shadows), child: Center(child: content));
  }

  Widget _buildTrackingBar(ThemeData theme) {
    return Container(padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10), color: theme.cardColor, child: Row(children: [
      AnimatedBuilder(animation: _pulseController, builder: (context, _) => Container(width: 10, height: 10, decoration: BoxDecoration(color: _carLocation != null ? Color.lerp(Colors.green.shade900, Colors.green, _pulseController.value) : Colors.orange, shape: BoxShape.circle))),
      const SizedBox(width: 8),
      Expanded(child: _carLocation != null ? Text('🚗 Zone ${_carLocation!.zone}', style: theme.textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w500), overflow: TextOverflow.ellipsis) : const Text('Waiting for camera...', style: TextStyle(color: Colors.orange, fontSize: 13))),
    ]));
  }

  Widget _buildLegend(ThemeData theme) {
    final isDark = theme.brightness == Brightness.dark;
    return Container(padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6), child: Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [
      _legendItem(const Color(0xFF14C8A1), 'Target', theme), _legendItem(const Color(0xFFFFD600), 'Path', theme), _legendItem(const Color(0xFF2979FF), 'Car', theme), _legendItem(Colors.green.withOpacity(0.3), 'Passed', theme), _legendItem(isDark ? const Color(0xFF1A1F38) : Colors.white, 'Slot', theme, border: true),
    ]));
  }

  Widget _legendItem(Color color, String label, ThemeData theme, {bool border = false}) {
    return Row(children: [Container(width: 12, height: 12, decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(3), border: border ? Border.all(color: theme.dividerColor) : null)), const SizedBox(width: 3), Text(label, style: TextStyle(fontSize: 10, fontWeight: FontWeight.w500, color: theme.textTheme.bodyMedium?.color))]);
  }

  Widget _buildInfoBar(ThemeData theme) {
    return Container(padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14), decoration: BoxDecoration(color: theme.cardColor, border: Border(top: BorderSide(color: theme.dividerColor))), child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('🅿️ ${widget.slotId}', style: TextStyle(color: theme.colorScheme.primary, fontSize: 18, fontWeight: FontWeight.bold)),
        if (_navData != null) Text('Row ${_navData!.destination.row}, Col ${_navData!.destination.col}', style: TextStyle(color: theme.textTheme.bodySmall?.color, fontSize: 11)),
      ]),
      ElevatedButton.icon(onPressed: () => Navigator.pop(context), icon: const Icon(Icons.home, size: 18), label: const Text('Done', style: TextStyle(fontWeight: FontWeight.bold))),
    ]));
  }
}
