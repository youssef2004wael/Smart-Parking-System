import 'dart:async';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../services/secure_storage_service.dart';
import '../parking_page.dart';
import 'login_page.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> with SingleTickerProviderStateMixin {
  double carPosition = -150;
  final SecureStorageService _storage = SecureStorageService();
  late AnimationController _fadeController;

  @override
  void initState() {
    super.initState();
    _fadeController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
    )..forward();

    WidgetsBinding.instance.addPostFrameCallback((_) {
      setState(() {
        carPosition = 230;
      });
    });

    Timer(const Duration(seconds: 3), () {
      _checkAuthAndNavigate();
    });
  }

  @override
  void dispose() {
    _fadeController.dispose();
    super.dispose();
  }

  Future<void> _checkAuthAndNavigate() async {
    final token = await _storage.readAccessToken();

    if (!mounted) return;

    if (token != null && token.isNotEmpty) {
      try {
        // Validate token with server instead of blindly trusting it
        final authProvider = context.read<AuthProvider>();
        await authProvider.fetchProfile();
        
        if (authProvider.isLoggedIn && mounted) {
          Navigator.pushReplacement(
            context,
            MaterialPageRoute(builder: (_) => const ParkingPage()),
          );
        } else {
          // Token is invalid/expired, clear and go to login
          await authProvider.logout();
          if (mounted) {
            Navigator.pushReplacement(
              context,
              MaterialPageRoute(builder: (_) => const LoginPage()),
            );
          }
        }
      } catch (e) {
        // Server error or invalid token, clear storage and go to login
        await _storage.clearTokens();
        if (mounted) {
          Navigator.pushReplacement(
            context,
            MaterialPageRoute(builder: (_) => const LoginPage()),
          );
        }
      }
    } else {
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => const LoginPage()),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return Scaffold(
      backgroundColor: isDark ? const Color(0xFF0A0E21) : Colors.white,
      body: Stack(
        children: [
          Center(
            child: FadeTransition(
              opacity: _fadeController,
              child: Image.asset('assets/logo.png', width: 300, height: 300),
            ),
          ),
          AnimatedPositioned(
            duration: const Duration(seconds: 2),
            curve: Curves.easeInOut,
            bottom: 20,
            left: carPosition,
            child: Image.asset('assets/car.png', width: 120, height: 120),
          ),
          Positioned(
            bottom: 0,
            left: 0,
            right: 0,
            child: Image.asset(
              'assets/road.jpg',
              width: MediaQuery.of(context).size.width,
              height: 50,
              fit: BoxFit.fill,
            ),
          ),
          Positioned(
            bottom: 40,
            right: 0,
            child: Image.asset('assets/halfhouse.png', width: 120, height: 120),
          ),
          Positioned(
            bottom: 45,
            right: 55,
            child: Image.asset('assets/p.png', width: 60, height: 60),
          ),
        ],
      ),
    );
  }
}
