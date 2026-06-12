import 'dart:async';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import 'models/parking_slot.dart' as model;
import 'models/reservation.dart';
import 'providers/parking_provider.dart';
import 'providers/locale_provider.dart';
import 'screens/booking_page.dart';
import 'screens/profile_page.dart';
import 'screens/navigation_page.dart';
import 'models/parking_slot.dart';
import 'widgets/parking_lane.dart';
import 'utils/app_strings.dart';
import 'services/notification_service.dart';

class ParkingPage extends StatefulWidget {
  const ParkingPage({super.key});

  @override
  State<ParkingPage> createState() => _ParkingPageState();
}

class _ParkingPageState extends State<ParkingPage> with WidgetsBindingObserver {
  Timer? _countdownTimer;
  Timer? _slotsRefreshTimer;
  bool _wasActive = false;
  bool _hasArrivedAtSlot = false;
  bool _isHandlingExpiry = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    Future.microtask(() {
      context.read<ParkingProvider>().loadReservations();
    });
    _countdownTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted) return;
      final provider = context.read<ParkingProvider>();
      final active = _getActiveReservation(provider);

      if (_wasActive && active == null && !_isHandlingExpiry) {
        if (kDebugMode) print('🔴 EXPIRED DETECTED! Triggering cleanup...');
        _isHandlingExpiry = true;
        _handleExpiry(provider);
      } else if (active != null) {
        _wasActive = true;
      }
      setState(() {});
    });
  }

  Future<void> _handleExpiry(ParkingProvider provider) async {
    if (kDebugMode) print('🔄 Step 1: Waiting 2s for backend to catch up...');
    await Future.delayed(const Duration(seconds: 2));
    if (!mounted) return;

    if (kDebugMode) print('🔄 Step 2: Calling cleanup API...');
    await provider.handleReservationExpired();
    if (!mounted) return;

    bool stillHasIssue = provider.slots.any((s) => s.status == 'reserved');
    if (stillHasIssue) {
      if (kDebugMode) print('⚠️ Still has reserved slots, retrying in 3s...');
      await Future.delayed(const Duration(seconds: 3));
      if (mounted) {
        await provider.handleReservationExpired();
      }
    }

    if (kDebugMode) {
      for (final s in provider.slots) {
        if (s.status == 'reserved') {
          print('   ⚠️ STILL RESERVED: ${s.slotNumber}');
        }
      }
      print('✅ Cleanup complete.');
    }

    if (mounted) {
      setState(() {
        _wasActive = false;
        _isHandlingExpiry = false;
      });
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _countdownTimer?.cancel();
    _slotsRefreshTimer?.cancel();
    NotificationService().stopMonitor();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      context.read<ParkingProvider>().handleReservationExpired();
    }
  }

  Reservation? _getActiveReservation(ParkingProvider provider) {
    try {
      return provider.reservations.firstWhere(
        (r) => r.isActive && !r.isExpired && !provider.isLocallyCancelled(r.id),
      );
    } catch (_) {
      return null;
    }
  }

  void _startSlotsRefresh() {
    if (_slotsRefreshTimer != null) return;
    _slotsRefreshTimer = Timer.periodic(const Duration(seconds: 15), (_) {
      if (!mounted) return;
      if (kDebugMode) print('🔄 Auto-refreshing slots...');
      context.read<ParkingProvider>().handleReservationExpired();
    });
  }

  void _stopSlotsRefresh() {
    _slotsRefreshTimer?.cancel();
    _slotsRefreshTimer = null;
  }

  @override
  Widget build(BuildContext context) {
    return Consumer2<ParkingProvider, LocaleProvider>(
      builder: (context, provider, localeProvider, _) {
        final activeReservation = _getActiveReservation(provider);
        final lang = localeProvider.locale.languageCode;

        if (activeReservation != null) {
          _stopSlotsRefresh();
          NotificationService().startReservationMonitor(
            activeReservation.endTime,
            lang: lang,
          );
          return _buildActiveBookingScreen(context, provider, activeReservation, lang);
        } else {
          _startSlotsRefresh();
          NotificationService().stopMonitor();
          return _buildSlotsScreen(context, provider, lang);
        }
      },
    );
  }

  Widget _buildActiveBookingScreen(
      BuildContext context, ParkingProvider provider, Reservation r, String lang) {
    final theme = Theme.of(context);
    final remaining = r.remainingTime;
    final hours = remaining.inHours;
    final minutes = remaining.inMinutes % 60;
    final seconds = remaining.inSeconds % 60;
    final countdownText =
        '${hours.toString().padLeft(2, '0')}:${minutes.toString().padLeft(2, '0')}:${seconds.toString().padLeft(2, '0')}';
    final isLowTime = remaining.inMinutes < 5;
    final totalDuration = r.endTime.difference(r.startTime).inSeconds;
    final progress = totalDuration > 0
        ? 1.0 - (remaining.inSeconds / totalDuration)
        : 1.0;

    return Directionality(
      textDirection: lang == 'ar' ? ui.TextDirection.rtl : ui.TextDirection.ltr,
      child: Scaffold(
        appBar: AppBar(
          title: Text(AppStrings.get('myParking', lang)),
          actions: [
            IconButton(
              icon: const Icon(Icons.person_outline),
              onPressed: () => Navigator.push(
                  context, MaterialPageRoute(builder: (_) => const ProfilePage())),
            ),
          ],
        ),
        body: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(
            children: [
              const SizedBox(height: 10),
              Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: (isLowTime ? Colors.red : theme.colorScheme.primary)
                      .withOpacity(0.1),
                  shape: BoxShape.circle,
                ),
                child: Icon(
                  isLowTime ? Icons.timer_off : Icons.local_parking,
                  size: 50,
                  color: isLowTime ? Colors.red : theme.colorScheme.primary,
                ),
              ),
              const SizedBox(height: 16),
              Text(AppStrings.get('activeReservation', lang),
                  style: theme.textTheme.titleLarge),
              const SizedBox(height: 24),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: isLowTime
                        ? [const Color(0xFFE53935), const Color(0xFFC62828)]
                        : [const Color(0xFF0D7377), const Color(0xFF14C8A1)],
                  ),
                  borderRadius: BorderRadius.circular(20),
                  boxShadow: [
                    BoxShadow(
                      color: (isLowTime ? Colors.red : theme.colorScheme.primary)
                          .withOpacity(0.3),
                      blurRadius: 15,
                      offset: const Offset(0, 8),
                    ),
                  ],
                ),
                child: Column(
                  children: [
                    Text(AppStrings.get('timeRemaining', lang),
                        style: const TextStyle(color: Colors.white70, fontSize: 14,
                            letterSpacing: 2, fontWeight: FontWeight.w500)),
                    const SizedBox(height: 12),
                    Text(countdownText,
                        style: const TextStyle(fontSize: 48, fontWeight: FontWeight.bold,
                            fontFamily: 'monospace', color: Colors.white)),
                    const SizedBox(height: 16),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(10),
                      child: LinearProgressIndicator(
                        value: progress.clamp(0.0, 1.0),
                        backgroundColor: Colors.white24,
                        valueColor: const AlwaysStoppedAnimation<Color>(Colors.white),
                        minHeight: 6,
                      ),
                    ),
                    if (isLowTime) ...[
                      const SizedBox(height: 8),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(Icons.warning_amber, color: Colors.white, size: 16),
                          const SizedBox(width: 4),
                          Text(AppStrings.get('expiringSoon', lang),
                              style: const TextStyle(color: Colors.white, fontSize: 13)),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: 20),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: theme.cardColor,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: theme.dividerColor),
                ),
                child: Column(
                  children: [
                    _infoRow(Icons.local_parking, AppStrings.get('slot', lang), r.slotNumber, theme),
                    Divider(height: 24, color: theme.dividerColor),
                    _infoRow(Icons.layers, AppStrings.get('floor', lang), '${r.floor}', theme),
                    Divider(height: 24, color: theme.dividerColor),
                    _infoRow(Icons.directions_car, AppStrings.get('licensePlate', lang), r.licensePlate, theme),
                    Divider(height: 24, color: theme.dividerColor),
                    _infoRow(Icons.confirmation_number, AppStrings.get('code', lang), r.reservationCode, theme),
                    Divider(height: 24, color: theme.dividerColor),
                    _infoRow(Icons.access_time, AppStrings.get('start', lang),
                        DateFormat('MMM d, hh:mm a').format(r.startTime), theme),
                    Divider(height: 24, color: theme.dividerColor),
                    _infoRow(Icons.timer_off, AppStrings.get('end', lang),
                        DateFormat('MMM d, hh:mm a').format(r.endTime), theme),
                  ],
                ),
              ),
              const SizedBox(height: 20),
              if (!_hasArrivedAtSlot)
              SizedBox(
                width: double.infinity, height: 52,
                child: ElevatedButton.icon(
                  onPressed: () async {
                    final result = await Navigator.push(context,
                        MaterialPageRoute(builder: (_) => NavigationPage(
                            slotId: r.slotNumber, licensePlate: r.licensePlate)));
                    if (result == true && mounted) {
                      setState(() { _hasArrivedAtSlot = true; });
                    }
                  },
                  icon: const Icon(Icons.navigation),
                  label: Text(AppStrings.get('navigateToSlot', lang),
                      style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF2979FF),
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                  ),
                ),
              ),
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity, height: 52,
                child: ElevatedButton.icon(
                  onPressed: () => _showExtendDialog(context, provider, r, lang),
                  icon: const Icon(Icons.add_alarm),
                  label: Text(AppStrings.get('extendReservation', lang),
                      style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFFFFA726),
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                  ),
                ),
              ),
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity, height: 52,
                child: OutlinedButton.icon(
                  onPressed: () => _cancelReservation(context, provider, r, lang),
                  icon: const Icon(Icons.cancel_outlined),
                  label: Text(AppStrings.get('cancelReservation', lang),
                      style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: Colors.red,
                    side: const BorderSide(color: Colors.red),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _infoRow(IconData icon, String label, String value, ThemeData theme) {
    return Row(
      children: [
        Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: theme.colorScheme.primary.withOpacity(0.08),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Icon(icon, color: theme.colorScheme.primary, size: 20),
        ),
        const SizedBox(width: 14),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: theme.textTheme.bodySmall),
            Text(value, style: theme.textTheme.titleMedium),
          ],
        ),
      ],
    );
  }

  Future<void> _showExtendDialog(
      BuildContext context, ParkingProvider provider, Reservation r, String lang) async {
    final theme = Theme.of(context);
    int selectedMinutes = 15;
    final result = await showDialog<int>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          backgroundColor: theme.cardColor,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: Text(AppStrings.get('extendReservation', lang)),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('${AppStrings.get('extendBy', lang)} $selectedMinutes ${AppStrings.get('minutes', lang)}',
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              const SizedBox(height: 16),
              Slider(
                value: selectedMinutes.toDouble(),
                min: 5, max: 120, divisions: 23,
                label: '$selectedMinutes min',
                activeColor: const Color(0xFFFFA726),
                onChanged: (v) => setDialogState(() => selectedMinutes = v.round()),
              ),
              const SizedBox(height: 8),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                children: [5, 15, 30, 60].map((m) => GestureDetector(
                  onTap: () => setDialogState(() => selectedMinutes = m),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: selectedMinutes == m
                          ? const Color(0xFFFFA726)
                          : theme.dividerColor,
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text('${m}m',
                        style: TextStyle(
                            color: selectedMinutes == m ? Colors.white : theme.textTheme.bodyMedium?.color,
                            fontWeight: FontWeight.bold)),
                  ),
                )).toList(),
              ),
            ],
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx),
                child: Text(AppStrings.get('cancel', lang))),
            ElevatedButton(
              onPressed: () => Navigator.pop(ctx, selectedMinutes),
              style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFFFFA726)),
              child: Text(AppStrings.get('confirm', lang),
                  style: const TextStyle(color: Colors.white)),
            ),
          ],
        ),
      ),
    );

    if (result != null && mounted) {
      final success = await provider.extendReservation(r.id, result);
      if (success && mounted) {
        await provider.handleReservationExpired(); // Force refresh after extend
      }
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(success
                ? AppStrings.get('extended', lang)
                : AppStrings.get('failedToExtend', lang)),
            backgroundColor: success ? Colors.green : Colors.red,
          ),
        );
      }
    }
  }

  Future<void> _cancelReservation(
      BuildContext context, ParkingProvider provider, Reservation r, String lang) async {
    final theme = Theme.of(context);
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: theme.cardColor,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Text(AppStrings.get('cancelReservationQ', lang)),
        content: Text('${AppStrings.get('slot', lang)}: ${r.slotNumber}'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false),
              child: Text(AppStrings.get('keep', lang))),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: Text(AppStrings.get('cancelIt', lang),
                style: const TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
    if (confirm == true && mounted) {
      final success = await provider.cancelReservation(r.id);
      if (success && mounted) {
        await provider.handleReservationExpired(); // Force refresh after cancel
      }
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(success
                ? AppStrings.get('reservationCancelled', lang)
                : AppStrings.get('failedToCancel', lang)),
            backgroundColor: success ? Colors.green : Colors.red,
          ),
        );
      }
    }
  }

  Widget _buildSlotsScreen(BuildContext context, ParkingProvider provider, String lang) {
    final theme = Theme.of(context);
    return DefaultTabController(
      length: 3,
      child: Directionality(
        textDirection: lang == 'ar' ? ui.TextDirection.rtl : ui.TextDirection.ltr,
        child: Scaffold(
          appBar: AppBar(
            title: Text(AppStrings.get('parkingGarage', lang)),
            actions: [
              IconButton(
                icon: const Icon(Icons.refresh),
                onPressed: () {
                  provider.handleReservationExpired();
                },
              ),
              IconButton(
                icon: const Icon(Icons.person_outline),
                onPressed: () => Navigator.push(context,
                    MaterialPageRoute(builder: (_) => const ProfilePage())),
              ),
            ],
            bottom: TabBar(
              onTap: (i) => context.read<ParkingProvider>().setFloor(i.toString()),
              indicatorColor: theme.colorScheme.primary,
              labelColor: theme.colorScheme.primary,
              unselectedLabelColor: theme.textTheme.bodySmall?.color,
              tabs: [
                Tab(text: '${AppStrings.get('level', lang)} 1'),
                Tab(text: '${AppStrings.get('level', lang)} 2'),
                Tab(text: '${AppStrings.get('level', lang)} 3'),
              ],
            ),
          ),
          body: Consumer<ParkingProvider>(
            builder: (context, provider, _) {
              if (provider.isSlotsLoading) {
                return Center(child: CircularProgressIndicator(color: theme.colorScheme.primary));
              }
              final slots = provider.slots;
              if (slots.isEmpty) {
                return Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.local_parking, size: 64, color: theme.textTheme.bodySmall?.color),
                      const SizedBox(height: 16),
                      Text(AppStrings.get('noSlotsAvailable', lang),
                          style: theme.textTheme.bodyMedium),
                    ],
                  ),
                );
              }

              final colB = slots.where((s) => s.slotNumber.startsWith('B')).toList()..sort(_slotNumberComparator);
              final colC = slots.where((s) => s.slotNumber.startsWith('C')).toList()..sort(_slotNumberComparator);
              final colD = slots.where((s) => s.slotNumber.startsWith('D')).toList()..sort(_slotNumberComparator);
              final colA = slots.where((s) => s.slotNumber.startsWith('A')).toList()..sort(_slotNumberComparator);
              final int globalMaxRows = [colA.length, colB.length, colC.length, colD.length]
                  .reduce((a, b) => a > b ? a : b);
              final int laneArrowCount = globalMaxRows > 0 ? globalMaxRows : 1;

              return Column(
                children: [
                  _buildLegend(lang, theme),
                  const SizedBox(height: 4),
                  _buildGateIndicator(AppStrings.get('entrance', lang), Icons.login, theme),
                  const SizedBox(height: 4),
                  Expanded(
                    child: Center(
                      child: Container(
                        width: 340,
                        margin: const EdgeInsets.symmetric(horizontal: 12),
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 16),
                        decoration: BoxDecoration(
                          color: theme.cardColor,
                          borderRadius: BorderRadius.circular(28),
                          border: Border.all(color: theme.dividerColor),
                        ),
                        child: SingleChildScrollView(
                          child: Directionality(
                            textDirection: ui.TextDirection.ltr,
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Expanded(child: _buildSlotColumn(colA, provider, isLeftSkew: true)),
                                ParkingLane(arrowCount: laneArrowCount),
                                Expanded(child: _buildSlotColumn(colB, provider, isLeftSkew: false)),
                                Expanded(child: _buildSlotColumn(colC, provider, isLeftSkew: true)),
                                ParkingLane(arrowCount: laneArrowCount),
                                Expanded(child: _buildSlotColumn(colD, provider, isLeftSkew: false)),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                  _buildGateIndicator(AppStrings.get('exit', lang), Icons.logout, theme),
                  _buildConfirmButton(context, provider, lang, theme),
                ],
              );
            },
          ),
        ),
      ),
    );
  }

  Widget _buildLegend(String lang, ThemeData theme) {
    final isDark = theme.brightness == Brightness.dark;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        children: [
          _legendItem(isDark ? const Color(0xFF1A1F38) : Colors.white,
              AppStrings.get('available', lang), theme, border: true),
          _legendItem(const Color(0xFFE53935), AppStrings.get('occupied', lang), theme),
          _legendItem(const Color(0xFFFFA726), AppStrings.get('reserved', lang), theme),
          _legendItem(const Color(0xFF14C8A1), AppStrings.get('selected', lang), theme),
        ],
      ),
    );
  }

  Widget _legendItem(Color color, String label, ThemeData theme, {bool border = false}) {
    return Row(
      children: [
        Container(
          width: 14, height: 14,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(4),
            border: border ? Border.all(color: theme.dividerColor) : null,
          ),
        ),
        const SizedBox(width: 4),
        Text(label, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w500,
            color: theme.textTheme.bodyMedium?.color)),
      ],
    );
  }

  Widget _buildGateIndicator(String label, IconData icon, ThemeData theme) {
    return Column(
      children: [
        Text(label, style: TextStyle(fontWeight: FontWeight.bold,
            color: theme.textTheme.bodySmall?.color, fontSize: 10)),
        const Icon(Icons.arrow_downward, color: Color(0xFFFFA726), size: 18),
      ],
    );
  }

  Widget _buildSlotColumn(List<ParkingSlot> columnSlots, ParkingProvider provider,
      {required bool isLeftSkew}) {
    return Column(
      children: columnSlots.map<Widget>((slot) => DiagonalParkingSlot(
            slot: slot, isLeftSkew: isLeftSkew,
            isSelected: provider.selectedSlotId == _slotKey(slot),
            onTap: () => provider.selectSlot(_slotKey(slot)),
          )).toList(),
    );
  }

  Widget _buildConfirmButton(BuildContext context, ParkingProvider provider, String lang, ThemeData theme) {
    final bool hasSelection = provider.selectedSlotId != null;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 15),
      child: SizedBox(
        width: double.infinity, height: 55,
        child: ElevatedButton(
          onPressed: hasSelection ? () {
            final selectedSlot = provider.slots.firstWhere(
                (s) => _slotKey(s) == provider.selectedSlotId);
            Navigator.push(context, MaterialPageRoute(
              builder: (_) => BookingPage(
                slotId: selectedSlot.slotNumber,
                floor: provider.selectedFloor == '0' ? 'Ground' : 'Floor ${provider.selectedFloor}',
              ),
            )).then((_) {
              provider.handleReservationExpired();
            });
          } : null,
          style: ElevatedButton.styleFrom(
            backgroundColor: hasSelection ? theme.colorScheme.primary : theme.dividerColor,
            foregroundColor: Colors.white,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15)),
          ),
          child: Text(
            hasSelection ? AppStrings.get('confirmBooking', lang) : AppStrings.get('selectSlot', lang),
            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
          ),
        ),
      ),
    );
  }
}

String _slotKey(model.ParkingSlot slot) {
  return slot.slotId.isNotEmpty ? slot.slotId : slot.slotNumber;
}

int _slotNumberComparator(model.ParkingSlot a, model.ParkingSlot b) {
  int extractNumber(model.ParkingSlot s) {
    final match = RegExp(r'\d+').firstMatch(s.slotNumber);
    return match != null ? int.parse(match.group(0)!) : 0;
  }
  final na = extractNumber(a);
  final nb = extractNumber(b);
  if (na != nb) return na.compareTo(nb);
  return a.slotNumber.compareTo(b.slotNumber);
}

class DiagonalParkingSlot extends StatelessWidget {
  final model.ParkingSlot slot;
  final bool isLeftSkew;
  final bool isSelected;
  final VoidCallback onTap;

  const DiagonalParkingSlot({
    super.key, required this.slot, required this.isLeftSkew,
    required this.isSelected, required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    Color bgColor;
    bool canSelect = false;
    if (slot.status == 'occupied') {
      bgColor = const Color(0xFFE53935);
      canSelect = false;
    } else if (slot.status == 'reserved') {
      bgColor = const Color(0xFFFFA726);
      canSelect = false;
    } else if (isSelected) {
      bgColor = const Color(0xFF14C8A1);
      canSelect = true;
    } else {
      bgColor = isDark ? const Color(0xFF1A1F38) : Colors.white;
      canSelect = true;
    }

    final borderColor = isSelected
        ? const Color(0xFF0D7377)
        : (isDark ? const Color(0xFF2A2F48) : Colors.grey.shade300);

    return GestureDetector(
      onTap: canSelect ? onTap : null,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Transform(
          alignment: Alignment.center,
          transform: Matrix4.skewY(isLeftSkew ? -0.3 : 0.3),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            height: (slot.slotNumber.startsWith('B') || slot.slotNumber.startsWith('C')) ? 100.0 : 50.0,
            decoration: BoxDecoration(
              color: bgColor,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: borderColor, width: isSelected ? 2 : 1),
            ),
            child: Transform(
              alignment: Alignment.center,
              transform: Matrix4.skewY(isLeftSkew ? 0.3 : -0.3),
              child: Center(
                child: slot.status == 'occupied'
                    ? const Icon(Icons.directions_car, color: Colors.white, size: 18)
                    : Text(slot.slotNumber,
                        style: TextStyle(
                          color: _getTextColor(bgColor, isDark),
                          fontWeight: FontWeight.bold, fontSize: 12,
                        )),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Color _getTextColor(Color bgColor, bool isDark) {
    if (bgColor == const Color(0xFFE53935)) return Colors.white;
    if (bgColor == const Color(0xFF14C8A1)) return Colors.white;
    if (bgColor == const Color(0xFFFFA726)) return Colors.white;
    return isDark ? Colors.white : Colors.black;
  }
}
