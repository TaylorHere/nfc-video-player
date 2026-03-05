import 'dart:async';
import 'dart:convert';

import 'package:better_player_plus/better_player_plus.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:nfc_manager/nfc_manager.dart';

const _nfcControlChannel = MethodChannel('com.example.flutter_app/nfc_control');
const _defaultBackendBaseUrl = 'https://replace-with-your-worker-domain.workers.dev';

void main() {
  runApp(const MyApp());
}

class PlaybackDescriptor {
  final String type;
  final String? defaultUrl;
  final String? hlsUrl;
  final String? dashUrl;
  final Map<String, String> licenses;
  final Map<String, DrmSystemConfig> drmSystems;
  final String? sessionToken;

  const PlaybackDescriptor({
    required this.type,
    required this.defaultUrl,
    required this.hlsUrl,
    required this.dashUrl,
    required this.licenses,
    required this.drmSystems,
    this.sessionToken,
  });

  bool get isDrm => type.toLowerCase() == 'drm';

  String get primaryUrl => defaultUrl ?? hlsUrl ?? dashUrl ?? '';

  factory PlaybackDescriptor.file(String url) {
    return PlaybackDescriptor(
      type: 'file',
      defaultUrl: url,
      hlsUrl: null,
      dashUrl: null,
      licenses: const {},
      drmSystems: const {},
    );
  }

  DrmSystemConfig? system(String name) => drmSystems[name.toLowerCase()];

  factory PlaybackDescriptor.fromMap(Map<String, dynamic> map) {
    final rawLicenses = map['licenses'];
    final licenses = <String, String>{};
    if (rawLicenses is Map) {
      for (final entry in rawLicenses.entries) {
        final value = entry.value;
        if (value == null) continue;
        licenses[entry.key.toString().toLowerCase()] = value.toString();
      }
    }

    final systems = <String, DrmSystemConfig>{};
    final rawSystems = map['drm'];
    if (rawSystems is Map) {
      for (final entry in rawSystems.entries) {
        final key = entry.key.toString().toLowerCase();
        final value = entry.value;
        if (value is! Map) continue;
        systems[key] = DrmSystemConfig.fromMap(Map<String, dynamic>.from(value));
      }
    }

    for (final entry in licenses.entries) {
      systems.putIfAbsent(
        entry.key,
        () => DrmSystemConfig(licenseUrl: entry.value, certificateUrl: null, headers: const {}),
      );
    }

    return PlaybackDescriptor(
      type: (map['type'] ?? 'file').toString(),
      defaultUrl: map['default_url']?.toString(),
      hlsUrl: map['hls_url']?.toString(),
      dashUrl: map['dash_url']?.toString(),
      licenses: licenses,
      drmSystems: systems,
      sessionToken: map['session_token']?.toString(),
    );
  }
}

class DrmSystemConfig {
  final String? licenseUrl;
  final String? certificateUrl;
  final Map<String, String> headers;

  const DrmSystemConfig({
    required this.licenseUrl,
    required this.certificateUrl,
    required this.headers,
  });

  bool get hasLicense => licenseUrl != null && licenseUrl!.isNotEmpty;

  factory DrmSystemConfig.fromMap(Map<String, dynamic> map) {
    final rawHeaders = map['headers'];
    final headers = <String, String>{};
    if (rawHeaders is Map) {
      for (final entry in rawHeaders.entries) {
        final key = entry.key.toString().trim();
        final value = entry.value?.toString() ?? '';
        if (key.isEmpty) continue;
        headers[key] = value;
      }
    }

    return DrmSystemConfig(
      licenseUrl: map['license_url']?.toString(),
      certificateUrl: map['certificate_url']?.toString(),
      headers: headers,
    );
  }
}

class HistoryEntry {
  final String sourceUrl;
  final PlaybackDescriptor playback;
  final DateTime time;

  const HistoryEntry({
    required this.sourceUrl,
    required this.playback,
    required this.time,
  });
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'NFC Secure Player',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark(useMaterial3: true),
      home: const MainScreen(),
    );
  }
}

class MainScreen extends StatefulWidget {
  const MainScreen({super.key});

  @override
  State<MainScreen> createState() => _MainScreenState();
}

class _MainScreenState extends State<MainScreen> {
  int _currentIndex = 0;
  final List<HistoryEntry> _history = [];

  void _addHistory(HistoryEntry entry) {
    setState(() => _history.insert(0, entry));
  }

  @override
  Widget build(BuildContext context) {
    final pages = [
      ScanPage(onResolvedPlayback: _addHistory),
      HistoryPage(history: _history),
    ];

    return Scaffold(
      body: pages[_currentIndex],
      bottomNavigationBar: NavigationBar(
        selectedIndex: _currentIndex,
        onDestinationSelected: (value) => setState(() => _currentIndex = value),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.nfc), label: '扫描'),
          NavigationDestination(icon: Icon(Icons.history), label: '历史'),
        ],
      ),
    );
  }
}

class ScanPage extends StatefulWidget {
  final ValueChanged<HistoryEntry> onResolvedPlayback;

  const ScanPage({super.key, required this.onResolvedPlayback});

  @override
  State<ScanPage> createState() => _ScanPageState();
}

class _ScanPageState extends State<ScanPage> with SingleTickerProviderStateMixin {
  final String _fallbackBackendBaseUrl = _defaultBackendBaseUrl;

  late final AnimationController _pulseController;
  bool _isScanning = false;
  bool _isLocked = false;
  bool _isResolving = false;
  String _statusMessage = '长按下方按钮开始扫描';
  Timer? _holdTimer;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _holdTimer?.cancel();
    _pulseController.dispose();
    super.dispose();
  }

  Future<void> _enableNfcGate() async {
    try {
      await _nfcControlChannel.invokeMethod('enableNfc');
    } catch (_) {}
  }

  Future<void> _disableNfcGate() async {
    try {
      await _nfcControlChannel.invokeMethod('disableNfc');
    } catch (_) {}
  }

  void _onPressStart() {
    if (_isLocked || _isResolving) return;
    _startScanning();
    _holdTimer = Timer(const Duration(milliseconds: 1500), () {
      if (!mounted) return;
      setState(() {
        _isLocked = true;
        _statusMessage = '已锁定扫描，继续贴卡...';
      });
    });
  }

  void _onPressEnd() {
    _holdTimer?.cancel();
    if (!_isLocked) {
      _stopScanning();
    }
  }

  Future<void> _startScanning() async {
    if (_isScanning || _isResolving) return;

    final available = await NfcManager.instance.isAvailable();
    if (!available) {
      _showError('设备不支持 NFC');
      return;
    }

    await _enableNfcGate();
    if (!mounted) return;
    setState(() {
      _isScanning = true;
      _statusMessage = '扫描中，请将手机靠近 NFC 标签';
    });

    try {
      await NfcManager.instance.startSession(
        onDiscovered: (tag) async {
          if (_isResolving) return;
          _isResolving = true;
          try {
            final ndefUrl = _extractUrlFromTag(tag);
            if (ndefUrl == null) {
              final uid = _extractUidFromTag(tag);
              if (uid != null && mounted) {
                setState(() => _statusMessage = '已读取 UID: $uid，但没有 URL');
              }
              return;
            }

            if (mounted) {
              setState(() => _statusMessage = '已读取链接，正在验证并获取播放会话...');
            }
            await _resolveAndOpenPlayback(ndefUrl);
          } finally {
            _isResolving = false;
          }
        },
        onError: (error) async {
          _stopScanning();
          _showError('扫描失败: $error');
        },
      );
    } catch (e) {
      _stopScanning();
      _showError('启动扫描失败: $e');
    }
  }

  Future<void> _stopScanning() async {
    await _disableNfcGate();
    try {
      await NfcManager.instance.stopSession();
    } catch (_) {}

    if (!mounted) return;
    setState(() {
      _isScanning = false;
      _isLocked = false;
      if (_statusMessage.contains('扫描')) {
        _statusMessage = '长按下方按钮开始扫描';
      }
    });
  }

  static const List<String> _ndefPrefixes = [
    '',
    'http://www.',
    'https://www.',
    'http://',
    'https://',
    'tel:',
    'mailto:',
    'ftp://anonymous:anonymous@',
    'ftp://ftp.',
    'ftps://',
    'sftp://',
    'smb://',
    'nfs://',
    'ftp://',
    'dav://',
    'news:',
    'telnet://',
    'imap:',
    'rtsp://',
    'urn:',
    'pop:',
    'sip:',
    'sips:',
    'tftp:',
    'btspp://',
    'btl2cap://',
    'btgoep://',
    'tcpobex://',
    'irdaobex://',
    'file://',
    'urn:epc:id:',
    'urn:epc:tag:',
    'urn:epc:pat:',
    'urn:epc:raw:',
    'urn:epc:',
    'urn:nfc:',
  ];

  String? _extractUrlFromTag(NfcTag tag) {
    final ndef = Ndef.from(tag);
    final message = ndef?.cachedMessage;
    if (message == null) return null;

    for (final record in message.records) {
      if (record.typeNameFormat != NdefTypeNameFormat.nfcWellknown) continue;
      if (record.type.length != 1 || record.type.first != 0x55) continue;
      if (record.payload.isEmpty) continue;

      final prefixCode = record.payload.first;
      final payload = utf8.decode(record.payload.sublist(1), allowMalformed: true);
      final prefix = (prefixCode >= 0 && prefixCode < _ndefPrefixes.length)
          ? _ndefPrefixes[prefixCode]
          : '';
      final fullUrl = (prefix + payload).trim();
      if (fullUrl.isNotEmpty) return fullUrl;
    }
    return null;
  }

  String? _extractUidFromTag(NfcTag tag) {
    final data = tag.data;
    List<int>? uid;
    if (data['isodep']?['identifier'] is List) {
      uid = List<int>.from(data['isodep']['identifier']);
    } else if (data['nfca']?['identifier'] is List) {
      uid = List<int>.from(data['nfca']['identifier']);
    } else if (data['mifare']?['identifier'] is List) {
      uid = List<int>.from(data['mifare']['identifier']);
    }
    if (uid == null || uid.isEmpty) return null;
    return uid.map((b) => b.toRadixString(16).padLeft(2, '0')).join('').toUpperCase();
  }

  bool _looksLikeSecureNfcUrl(String rawUrl) {
    final uri = Uri.tryParse(rawUrl);
    if (uri == null) return false;
    return uri.queryParameters.containsKey('p') && uri.queryParameters.containsKey('m');
  }

  Uri _buildVerifyUri(String nfcUrl) {
    final parsed = Uri.parse(nfcUrl);
    final p = parsed.queryParameters['p'];
    final m = parsed.queryParameters['m'];
    if (p == null || m == null) {
      throw const FormatException('NFC 链接缺少 p/m 参数');
    }

    if (parsed.path.endsWith('/verify')) {
      return parsed.replace(queryParameters: {'p': p, 'm': m}, fragment: '');
    }

    if (parsed.hasAuthority && parsed.host.toLowerCase() != 'deo.app') {
      return parsed.replace(
        path: '/verify',
        queryParameters: {'p': p, 'm': m},
        fragment: '',
      );
    }

    final backendBase = Uri.parse(_fallbackBackendBaseUrl);
    return backendBase.replace(
      path: '/verify',
      queryParameters: {'p': p, 'm': m},
      fragment: '',
    );
  }

  Future<PlaybackDescriptor> _fetchPlaybackDescriptor(String streamUrl) async {
    final streamUri = Uri.parse(streamUrl);
    if (!streamUri.path.endsWith('/stream')) {
      return PlaybackDescriptor.file(streamUrl);
    }

    final query = Map<String, String>.from(streamUri.queryParameters);
    query['mode'] = 'json';
    final descriptorUri = streamUri.replace(queryParameters: query, fragment: '');

    try {
      final response = await http.get(descriptorUri).timeout(const Duration(seconds: 8));
      if (response.statusCode != 200) {
        return PlaybackDescriptor.file(streamUrl);
      }

      final payload = jsonDecode(response.body);
      if (payload is! Map<String, dynamic>) {
        return PlaybackDescriptor.file(streamUrl);
      }
      final playback = payload['playback'];
      if (playback is! Map<String, dynamic>) {
        return PlaybackDescriptor.file(streamUrl);
      }
      return PlaybackDescriptor.fromMap(playback);
    } catch (_) {
      return PlaybackDescriptor.file(streamUrl);
    }
  }

  Future<void> _resolveAndOpenPlayback(String nfcUrl) async {
    try {
      final descriptor = await (() async {
        if (_looksLikeSecureNfcUrl(nfcUrl)) {
          final verifyUri = _buildVerifyUri(nfcUrl);
          final response = await http.get(verifyUri).timeout(const Duration(seconds: 8));
          if (response.statusCode != 200) {
            throw Exception('验证失败: HTTP ${response.statusCode}');
          }

          final payload = jsonDecode(response.body);
          if (payload is! Map<String, dynamic> || payload['success'] != true) {
            final error = (payload is Map<String, dynamic>) ? payload['error'] : null;
            throw Exception('验证失败: ${error ?? "未知错误"}');
          }

          final streamUrl = payload['video_url']?.toString();
          if (streamUrl == null || streamUrl.isEmpty) {
            throw Exception('后端未返回可播放地址');
          }
          return _fetchPlaybackDescriptor(streamUrl);
        }

        final uri = Uri.tryParse(nfcUrl);
        if (uri == null || !uri.hasScheme) {
          throw Exception('NFC 链接格式无效');
        }
        return PlaybackDescriptor.file(nfcUrl);
      })();

      if (descriptor.primaryUrl.isEmpty) {
        throw Exception('无可用播放地址');
      }

      if (!mounted) return;
      await _stopScanning();

      final entry = HistoryEntry(
        sourceUrl: nfcUrl,
        playback: descriptor,
        time: DateTime.now(),
      );
      widget.onResolvedPlayback(entry);

      if (!mounted) return;
      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => VideoPlayerScreen(
            playback: descriptor,
            sourceUrl: nfcUrl,
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      _showError(e.toString());
    }
  }

  void _showError(String message) {
    setState(() => _statusMessage = message);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: Colors.red,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final iconColor = _isScanning ? Colors.greenAccent : Colors.white;
    return Scaffold(
      appBar: AppBar(title: const Text('NFC 安全播放')),
      body: Stack(
        children: [
          Positioned.fill(
            child: DecoratedBox(
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [Color(0xFF1B1234), Colors.black],
                ),
              ),
            ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const SizedBox(height: 16),
                  Text(
                    _statusMessage,
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 16, color: Colors.white70),
                  ),
                  const Spacer(),
                  GestureDetector(
                    behavior: HitTestBehavior.opaque,
                    onTapDown: (_) => _onPressStart(),
                    onTapUp: (_) => _onPressEnd(),
                    onTapCancel: _onPressEnd,
                    child: Center(
                      child: AnimatedBuilder(
                        animation: _pulseController,
                        builder: (context, child) {
                          final scale = _isScanning ? 1.0 + _pulseController.value * 0.08 : 1.0;
                          return Transform.scale(scale: scale, child: child);
                        },
                        child: Container(
                          width: 110,
                          height: 110,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: Colors.white.withOpacity(_isScanning ? 0.12 : 0.06),
                            border: Border.all(color: iconColor, width: 3),
                            boxShadow: [
                              BoxShadow(
                                color: iconColor.withOpacity(0.35),
                                blurRadius: 20,
                                spreadRadius: 2,
                              ),
                            ],
                          ),
                          child: Icon(
                            _isScanning ? Icons.wifi_tethering : Icons.nfc,
                            color: iconColor,
                            size: 48,
                          ),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  Center(
                    child: Text(
                      _isScanning ? '松手可停止扫描' : '长按开始扫描',
                      style: const TextStyle(color: Colors.white54),
                    ),
                  ),
                  const SizedBox(height: 40),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class HistoryPage extends StatelessWidget {
  final List<HistoryEntry> history;

  const HistoryPage({super.key, required this.history});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('播放历史')),
      body: history.isEmpty
          ? const Center(child: Text('暂无历史记录', style: TextStyle(color: Colors.grey)))
          : ListView.separated(
              itemCount: history.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (context, index) {
                final item = history[index];
                return ListTile(
                  leading: Icon(
                    item.playback.isDrm ? Icons.verified_user : Icons.movie,
                    color: item.playback.isDrm ? Colors.greenAccent : Colors.deepPurpleAccent,
                  ),
                  title: Text(
                    item.playback.primaryUrl,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  subtitle: Text(
                    '${item.playback.isDrm ? "DRM" : "FILE"} · ${item.time.toLocal()}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  onTap: () {
                    Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => VideoPlayerScreen(
                          playback: item.playback,
                          sourceUrl: item.sourceUrl,
                        ),
                      ),
                    );
                  },
                );
              },
            ),
    );
  }
}

class _PlayableSource {
  final String url;
  final BetterPlayerDrmConfiguration? drmConfiguration;

  const _PlayableSource({
    required this.url,
    this.drmConfiguration,
  });
}

class VideoPlayerScreen extends StatefulWidget {
  final PlaybackDescriptor playback;
  final String sourceUrl;

  const VideoPlayerScreen({
    super.key,
    required this.playback,
    required this.sourceUrl,
  });

  @override
  State<VideoPlayerScreen> createState() => _VideoPlayerScreenState();
}

class _VideoPlayerScreenState extends State<VideoPlayerScreen> {
  BetterPlayerController? _controller;
  String? _errorMessage;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _initializePlayer();
  }

  @override
  void dispose() {
    _controller?.dispose();
    super.dispose();
  }

  BetterPlayerVideoFormat _inferVideoFormat(String url) {
    final lower = url.toLowerCase();
    if (lower.contains('.m3u8')) return BetterPlayerVideoFormat.hls;
    if (lower.contains('.mpd')) return BetterPlayerVideoFormat.dash;
    return BetterPlayerVideoFormat.other;
  }

  _PlayableSource? _pickSourceForCurrentPlatform() {
    final descriptor = widget.playback;
    if (!descriptor.isDrm) {
      if (descriptor.primaryUrl.isEmpty) return null;
      return _PlayableSource(url: descriptor.primaryUrl);
    }

    final platform = defaultTargetPlatform;
    if (platform == TargetPlatform.android) {
      final widevineConfig =
          descriptor.system('widevine') ??
          DrmSystemConfig(
            licenseUrl: descriptor.licenses['widevine'],
            certificateUrl: null,
            headers: const {},
          );
      final mediaUrl = descriptor.dashUrl ?? descriptor.hlsUrl ?? descriptor.defaultUrl;
      if (mediaUrl != null && mediaUrl.isNotEmpty) {
        final drmConfig = (widevineConfig.hasLicense)
            ? BetterPlayerDrmConfiguration(
                drmType: BetterPlayerDrmType.widevine,
                licenseUrl: widevineConfig.licenseUrl!,
                headers: widevineConfig.headers.isEmpty ? null : widevineConfig.headers,
              )
            : null;
        return _PlayableSource(url: mediaUrl, drmConfiguration: drmConfig);
      }
    }

    if (platform == TargetPlatform.iOS) {
      final fairplayConfig =
          descriptor.system('fairplay') ??
          DrmSystemConfig(
            licenseUrl: descriptor.licenses['fairplay'],
            certificateUrl: null,
            headers: const {},
          );
      final mediaUrl = descriptor.hlsUrl ?? descriptor.defaultUrl ?? descriptor.dashUrl;
      if (mediaUrl != null && mediaUrl.isNotEmpty) {
        final drmConfig = (fairplayConfig.hasLicense)
            ? BetterPlayerDrmConfiguration(
                drmType: BetterPlayerDrmType.fairplay,
                licenseUrl: fairplayConfig.licenseUrl!,
                certificateUrl: fairplayConfig.certificateUrl,
                headers: fairplayConfig.headers.isEmpty ? null : fairplayConfig.headers,
              )
            : null;
        return _PlayableSource(url: mediaUrl, drmConfiguration: drmConfig);
      }
    }

    if (descriptor.primaryUrl.isEmpty) return null;
    return _PlayableSource(url: descriptor.primaryUrl);
  }

  Future<void> _initializePlayer() async {
    final source = _pickSourceForCurrentPlatform();
    if (source == null) {
      setState(() {
        _loading = false;
        _errorMessage = '没有可播放的媒体地址';
      });
      return;
    }

    try {
      final controller = BetterPlayerController(
        BetterPlayerConfiguration(
          autoPlay: true,
          fit: BoxFit.contain,
          allowedScreenSleep: false,
          handleLifecycle: true,
          controlsConfiguration: const BetterPlayerControlsConfiguration(
            enableSkips: false,
          ),
        ),
      );

      final dataSource = BetterPlayerDataSource(
        BetterPlayerDataSourceType.network,
        source.url,
        videoFormat: _inferVideoFormat(source.url),
        drmConfiguration: source.drmConfiguration,
      );

      await controller.setupDataSource(dataSource);
      if (!mounted) {
        controller.dispose();
        return;
      }
      setState(() {
        _controller = controller;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _errorMessage = '播放初始化失败: $e';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.playback.isDrm ? 'DRM 播放' : '视频播放'),
      ),
      backgroundColor: Colors.black,
      body: Column(
        children: [
          if (_loading)
            const Expanded(child: Center(child: CircularProgressIndicator()))
          else if (_errorMessage != null)
            Expanded(
              child: Center(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Text(
                    _errorMessage!,
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: Colors.redAccent),
                  ),
                ),
              ),
            )
          else if (_controller != null)
            Expanded(
              child: BetterPlayer(controller: _controller!),
            ),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            color: Colors.white.withOpacity(0.05),
            child: Text(
              '来源: ${widget.sourceUrl}\n播放地址: ${widget.playback.primaryUrl}',
              style: const TextStyle(fontSize: 12, color: Colors.white70),
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }
}
