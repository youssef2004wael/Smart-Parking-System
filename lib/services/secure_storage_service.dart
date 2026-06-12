import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class SecureStorageService {
  SecureStorageService({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  static const String _keyAccessToken = 'access_token';
  static const String _keyRefreshToken = 'refresh_token';

  final FlutterSecureStorage _storage;

  Future<void> saveTokens({
    required String accessToken,
    required String refreshToken,
  }) async {
    await _storage.write(key: _keyAccessToken, value: accessToken);
    await _storage.write(key: _keyRefreshToken, value: refreshToken);
  }

  Future<String?> readAccessToken() => _storage.read(key: _keyAccessToken);

  Future<String?> readRefreshToken() => _storage.read(key: _keyRefreshToken);

  Future<void> clearTokens() async {
    await _storage.delete(key: _keyAccessToken);
    await _storage.delete(key: _keyRefreshToken);
  }


  Future<void> addCancelledId(int id) async {
    final current = await readCancelledIds();
    current.add(id);
    await _storage.write(key: 'cancelled_ids', value: current.join(','));
  }

  Future<Set<int>> readCancelledIds() async {
    final raw = await _storage.read(key: 'cancelled_ids');
    if (raw == null || raw.isEmpty) return {};
    return raw.split(',').where((s) => s.isNotEmpty).map((s) => int.parse(s)).toSet();
  }
}