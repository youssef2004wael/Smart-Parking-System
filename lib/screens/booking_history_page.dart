import 'dart:ui' as ui;
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../providers/parking_provider.dart';
import '../providers/locale_provider.dart';
import '../models/reservation.dart';
import '../utils/app_strings.dart';

class BookingHistoryPage extends StatefulWidget {
  const BookingHistoryPage({super.key});

  @override
  State<BookingHistoryPage> createState() => _BookingHistoryPageState();
}

class _BookingHistoryPageState extends State<BookingHistoryPage> {
  Timer? _countdownTimer;

  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      context.read<ParkingProvider>().loadReservations();
    });
    _countdownTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _countdownTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<ParkingProvider>();
    final theme = Theme.of(context);
    final lang = context.watch<LocaleProvider>().locale.languageCode;

    // 🛠️ Smart Filtering: Ignore locally cancelled from Active, and force them into Past
    final active = provider.reservations
        .where((r) => r.isActive && !r.isExpired && !provider.isLocallyCancelled(r.id))
        .toList();
    final past = provider.reservations
        .where((r) => !r.isActive || r.isExpired || provider.isLocallyCancelled(r.id))
        .toList();

    return Directionality(
      textDirection: lang == 'ar' ? ui.TextDirection.rtl : ui.TextDirection.ltr,
      child: Scaffold(
        appBar: AppBar(
          title: Text(AppStrings.get('myBookings', lang)),
          actions: [
            IconButton(
              icon: const Icon(Icons.refresh),
              onPressed: () => provider.loadReservations(),
            ),
          ],
        ),
        body: provider.isReservationsLoading
            ? Center(child: CircularProgressIndicator(color: theme.colorScheme.primary))
            : provider.reservations.isEmpty
                ? _buildEmpty(theme, lang)
                : RefreshIndicator(
                    onRefresh: () => provider.loadReservations(),
                    child: ListView(
                      padding: const EdgeInsets.all(16),
                      children: [
                        if (active.isNotEmpty) ...[
                          _buildSectionHeader(
                              AppStrings.get('activeReservations', lang),
                              const Color(0xFF14C8A1), active.length, theme),
                          const SizedBox(height: 8),
                          ...active.map((r) => _buildActiveCard(r, theme, lang)),
                          const SizedBox(height: 20),
                        ],
                        if (past.isNotEmpty) ...[
                          _buildSectionHeader(
                              AppStrings.get('pastReservations', lang),
                              theme.textTheme.bodySmall?.color ?? Colors.grey, past.length, theme),
                          const SizedBox(height: 8),
                          ...past.map((r) => _buildPastCard(r, theme, lang, provider.isLocallyCancelled(r.id))),
                        ],
                      ],
                    ),
                  ),
      ),
    );
  }

  Widget _buildEmpty(ThemeData theme, String lang) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.event_busy, size: 64, color: theme.textTheme.bodySmall?.color),
          const SizedBox(height: 16),
          Text(AppStrings.get('noBookingsYet', lang), style: theme.textTheme.bodyMedium),
          const SizedBox(height: 8),
          Text(AppStrings.get('historyAppearHere', lang), style: theme.textTheme.bodySmall),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(String title, Color color, int count, ThemeData theme) {
    return Row(
      children: [
        Container(width: 4, height: 20,
          decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(2))),
        const SizedBox(width: 8),
        Text(title, style: theme.textTheme.titleMedium),
        const SizedBox(width: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
          decoration: BoxDecoration(
            color: color.withOpacity(0.15),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Text('$count',
              style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 12)),
        ),
      ],
    );
  }

  Widget _buildActiveCard(Reservation r, ThemeData theme, String lang) {
    final remaining = r.remainingTime;
    final hours = remaining.inHours;
    final minutes = remaining.inMinutes % 60;
    final seconds = remaining.inSeconds % 60;
    final countdownText =
        '${hours.toString().padLeft(2, '0')}:${minutes.toString().padLeft(2, '0')}:${seconds.toString().padLeft(2, '0')}';
    final isLowTime = remaining.inMinutes < 5;

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: theme.cardColor,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF14C8A1).withOpacity(0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: const Color(0xFF14C8A1).withOpacity(0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.local_parking, color: Color(0xFF14C8A1), size: 20),
                ),
                const SizedBox(width: 10),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('${AppStrings.get('slot', lang)} ${r.slotNumber}',
                        style: theme.textTheme.titleMedium),
                    Text('${AppStrings.get('floor', lang)} ${r.floor}',
                        style: theme.textTheme.bodySmall),
                  ],
                ),
              ]),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: const Color(0xFF14C8A1).withOpacity(0.1),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(AppStrings.get('active', lang),
                    style: const TextStyle(color: Color(0xFF14C8A1), fontWeight: FontWeight.bold, fontSize: 12)),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: isLowTime
                  ? Colors.red.withOpacity(0.1)
                  : theme.colorScheme.primary.withOpacity(0.08),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: isLowTime
                    ? Colors.red.withOpacity(0.3)
                    : theme.colorScheme.primary.withOpacity(0.2)),
            ),
            child: Column(
              children: [
                Text(AppStrings.get('timeRemaining', lang),
                    style: TextStyle(
                        color: isLowTime ? Colors.red : theme.colorScheme.primary,
                        fontSize: 12, fontWeight: FontWeight.w500)),
                const SizedBox(height: 6),
                Text(countdownText,
                    style: TextStyle(
                        fontSize: 32, fontWeight: FontWeight.bold, fontFamily: 'monospace',
                        color: isLowTime ? Colors.red : theme.colorScheme.primary)),
                if (isLowTime)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(Icons.warning_amber, size: 14, color: Colors.red),
                        const SizedBox(width: 4),
                        Text(AppStrings.get('expiringSoon', lang),
                            style: const TextStyle(color: Colors.red, fontSize: 12)),
                      ],
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(child: _detailItem(Icons.directions_car,
                AppStrings.get('licensePlate', lang), r.licensePlate, theme)),
            Expanded(child: _detailItem(Icons.confirmation_number,
                AppStrings.get('code', lang), r.reservationCode, theme)),
          ]),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(child: _detailItem(Icons.access_time,
                AppStrings.get('start', lang),
                DateFormat('MMM d, hh:mm a').format(r.startTime.toLocal()), theme)),
            Expanded(child: _detailItem(Icons.timer_off,
                AppStrings.get('end', lang),
                DateFormat('MMM d, hh:mm a').format(r.endTime.toLocal()), theme)),
          ]),
          const SizedBox(height: 14),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: () => _cancelReservation(r, lang),
              icon: const Icon(Icons.cancel_outlined, size: 18),
              label: Text(AppStrings.get('cancelReservation', lang)),
              style: OutlinedButton.styleFrom(
                foregroundColor: Colors.red,
                side: const BorderSide(color: Colors.red),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                padding: const EdgeInsets.symmetric(vertical: 12),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPastCard(Reservation r, ThemeData theme, String lang, bool isLocallyCancelled) {
    // 🛠️ If locally cancelled, force it to show as Cancelled even if backend is bugged
    final isCancelled = isLocallyCancelled || (!r.isActive && !r.isExpired);
    final statusText = isCancelled
        ? AppStrings.get('cancelled', lang)
        : AppStrings.get('expired', lang);
    final statusColor = isCancelled ? Colors.red : Colors.orange;

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: theme.cardColor,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: theme.dividerColor),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: theme.dividerColor,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(Icons.local_parking, color: theme.textTheme.bodySmall?.color, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('${AppStrings.get('slot', lang)} ${r.slotNumber} - ${AppStrings.get('floor', lang)} ${r.floor}',
                    style: theme.textTheme.titleMedium?.copyWith(
                      decoration: isCancelled ? TextDecoration.lineThrough : TextDecoration.none,
                    )),
                const SizedBox(height: 2),
                Text('${r.licensePlate} - ${DateFormat('MMM d, yyyy').format(r.startTime.toLocal())}',
                    style: theme.textTheme.bodySmall),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: statusColor.withOpacity(0.1),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Text(statusText,
                style: TextStyle(color: statusColor, fontWeight: FontWeight.bold, fontSize: 11)),
          ),
        ],
      ),
    );
  }

  Widget _detailItem(IconData icon, String label, String value, ThemeData theme) {
    return Row(
      children: [
        Icon(icon, size: 14, color: theme.textTheme.bodySmall?.color),
        const SizedBox(width: 4),
        Flexible(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: TextStyle(fontSize: 10, color: theme.textTheme.bodySmall?.color)),
              Text(value, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600,
                  color: theme.textTheme.bodyLarge?.color), overflow: TextOverflow.ellipsis),
            ],
          ),
        ),
      ],
    );
  }

  Future<void> _cancelReservation(Reservation r, String lang) async {
    final theme = Theme.of(context);
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: theme.cardColor,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Text(AppStrings.get('cancelReservationQ', lang)),
        content: Text('${AppStrings.get('slot', lang)}: ${r.slotNumber}\n${AppStrings.get('code', lang)}: ${r.reservationCode}'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false),
              child: Text(AppStrings.get('keep', lang))),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: Text(AppStrings.get('cancelIt', lang), style: const TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
    if (confirm == true && mounted) {
      final success = await context.read<ParkingProvider>().cancelReservation(r.id);
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
}
