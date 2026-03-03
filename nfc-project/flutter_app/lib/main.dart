import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:nfc_manager/nfc_manager.dart';
import 'package:video_player/video_player.dart';
import 'package:http/http.dart' as http;
import 'package:encrypt/encrypt.dart' as enc;

// NFC 控制通道
const _nfcControlChannel = MethodChannel('com.example.flutter_app/nfc_control');

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'NFC Video Player',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF6200EE),
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
        scaffoldBackgroundColor: const Color(0xFF121212),
      ),
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
  final List<String> _history = []; // In-memory history for now

  void _addToHistory(String url) {
    setState(() {
      if (!_history.contains(url)) {
        _history.insert(0, url);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final pages = [
      ScanPage(onUrlFound: _addToHistory),
      HistoryPage(history: _history),
    ];

    return Scaffold(
      body: pages[_currentIndex],
      bottomNavigationBar: NavigationBar(
        selectedIndex: _currentIndex,
        onDestinationSelected: (index) => setState(() => _currentIndex = index),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.nfc),
            label: '扫描',
          ),
          NavigationDestination(
            icon: Icon(Icons.history),
            label: '历史',
          ),
        ],
      ),
    );
  }
}

class ScanPage extends StatefulWidget {
  final Function(String) onUrlFound;
  const ScanPage({super.key, required this.onUrlFound});

  @override
  State<ScanPage> createState() => _ScanPageState();
}

class _ScanPageState extends State<ScanPage> with SingleTickerProviderStateMixin {
  bool _isScanning = false;
  String _statusMessage = '长按下方区域开始扫描';
  late AnimationController _animController;
  Timer? _holdTimer;
  bool _isLocked = false;
  
  // Encryption Config (Demo)
  final _encKey = enc.Key.fromUtf8('12345678901234567890123456789012');
  final _encIV = enc.IV.fromUtf8('1234567890123456');
  
  // 后端验证服务器地址 (SUN 安全方案)
  final String _backendUrl = 'http://192.168.50.114:8080';

  @override
  void initState() {
    super.initState();
    _animController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    );
  }

  @override
  void dispose() {
    _animController.dispose();
    _holdTimer?.cancel();
    super.dispose();
  }

  void _onPressStart() {
    if (_isLocked) return; // Already locked, ignore press

    _startScanning();
    _holdTimer = Timer(const Duration(seconds: 2), () {
      if (mounted) {
        setState(() {
          _isLocked = true;
          _statusMessage = '已锁定扫描模式\n请继续靠近卡片...';
        });
        // Feedback: maybe a small vibration or sound here if possible
      }
    });
  }

  void _onPressEnd() {
    _holdTimer?.cancel();
    if (!_isLocked) {
      // Released too early
      _stopScanning();
    }
    // If locked, do nothing (keep scanning)
  }

  void _startScanning() async {
    // Prevent multiple starts
    if (_isScanning) return;

    bool isAvailable = await NfcManager.instance.isAvailable();
    if (!isAvailable) {
      _showError('此设备不支持 NFC');
      return;
    }

    try {
      await _nfcControlChannel.invokeMethod('enableNfc');
    } catch (_) {}

    setState(() {
      _isScanning = true;
      _statusMessage = '正在扫描...\n请保持长按';
      _animController.forward(); // Fade in background
    });

    try {
      await NfcManager.instance.startSession(
        onDiscovered: (NfcTag tag) async {
          final ndef = Ndef.from(tag);
          if (ndef != null && ndef.cachedMessage != null) {
             for (var record in ndef.cachedMessage!.records) {
               if (record.typeNameFormat == NdefTypeNameFormat.nfcWellknown && 
                   record.type.length == 1 && record.type[0] == 0x55) { // 'U'
                 
                 String payload = utf8.decode(record.payload.sublist(1));
                 String prefix = _getNdefPrefix(record.payload[0]);
                 String fullUrl = prefix + payload;

                 if (fullUrl.startsWith('myenc://')) {
                   _handleEncryptedUrl(fullUrl);
                   return;
                 } else if (fullUrl.contains('deo.app/nfc')) {
                   _handleSunUrl(fullUrl); 
                   return;
                 } else if (fullUrl.startsWith('http')) {
                    _stopScanning();
                    _navigateToVideoPlayer(fullUrl);
                    return;
                 }
               }
             }
          }
          
          // Fallback: Read UID
          List<int> uidBytes = [];
          final data = tag.data;
          if (data.containsKey('isodep')) {
              uidBytes = List<int>.from(data['isodep']['identifier']);
          } else if (data.containsKey('nfca')) {
              uidBytes = List<int>.from(data['nfca']['identifier']);
          } else if (data.containsKey('mifare')) {
              uidBytes = List<int>.from(data['mifare']['identifier']);
          }

          if (uidBytes.isNotEmpty) {
            String uid = uidBytes.map((e) => e.toRadixString(16).padLeft(2, '0')).join('').toUpperCase();
            setState(() {
              _statusMessage = '读到卡片 UID: $uid\n(无有效内容)';
            });
            _stopScanning();
          }
        },
        onError: (e) async {
           // Only stop if not locked or if it's a fatal error?
           // Usually onError stops the session anyway.
           _stopScanning(); 
           _showError('扫描错误: $e');
        }
      );
    } catch (e) {
       _stopScanning();
       _showError('启动失败: $e');
    }
  }

  String _getNdefPrefix(int b) {
    const prefixes = [
      '', 'http://www.', 'https://www.', 'http://', 'https://', 'tel:', 'mailto:', 
      'ftp://anonymous:anonymous@', 'ftp://ftp.', 'ftps://', 'sftp://', 'smb://', 
      'nfs://', 'ftp://', 'dav://', 'news:', 'telnet://', 'imap:', 'rtsp://', 'urn:',
      'pop:', 'sip:', 'sips:', 'tftp:', 'btspp://', 'btl2cap://', 'btgoep://', 
      'tcpobex://', 'irdaobex://', 'file://', 'urn:epc:id:', 'urn:epc:tag:', 
      'urn:epc:pat:', 'urn:epc:raw:', 'urn:epc:', 'urn:nfc:'
    ];
    if (b >= 0 && b < prefixes.length) {
      return prefixes[b];
    }
    return '';
  }

  void _stopScanning() async {
    try {
      await _nfcControlChannel.invokeMethod('disableNfc');
    } catch (_) {}

    try {
      await NfcManager.instance.stopSession();
    } catch (_) {}
    
    if (mounted) {
      setState(() {
        _isScanning = false;
        _isLocked = false;
        _animController.stop();
        _animController.reverse(); // Fade out
        if (_statusMessage.contains('...')) {
           _statusMessage = '长按下方区域开始扫描';
        }
      });
    }
  }

  void _handleEncryptedUrl(String rawUrl) {
    _stopScanning();
    try {
      String hexData = rawUrl.replaceFirst('myenc://', '');
      final encrypter = enc.Encrypter(enc.AES(_encKey, mode: enc.AESMode.cbc));
      final encrypted = enc.Encrypted.fromBase16(hexData);
      final decryptedUrl = encrypter.decrypt(encrypted, iv: _encIV);

      _navigateToVideoPlayer(decryptedUrl);
    } catch (e) {
       _showError('解密失败: 数据可能被篡改');
    }
  }

  Future<void> _handleSunUrl(String sunUrl) async {
    // Keep scanning active visually but stop session logic if needed
    // Actually we should stop NFC session to prevent multi-reads
    _stopScanning();
    
    setState(() {
      _statusMessage = '正在验证卡片安全性...';
    });

    try {
      // Mock validation for UX demo if backend is offline
      // In production, remove this timeout and use real http call
      // await Future.delayed(Duration(seconds: 1)); 
      
      final response = await http.post(
        Uri.parse('$_backendUrl/verify'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'sun_data': sunUrl}),
      ).timeout(const Duration(seconds: 5), onTimeout: () {
        throw TimeoutException('连接服务器超时，请检查网络');
      });

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true && data['video_url'] != null) {
          _navigateToVideoPlayer(data['video_url']);
        } else {
          _showError('验证失败: ${data['error']}');
        }
      } else {
        _showError('服务器错误 (${response.statusCode})');
      }
    } catch (e) {
      if (mounted) {
        // Fallback for demo
        if (sunUrl.contains('deo.app')) {
           _showError('无法连接验证服务器\n$e');
        } else {
           _showError('网络错误: $e');
        }
      }
    }
  }

  void _navigateToVideoPlayer(String url) {
    widget.onUrlFound(url);
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (context) => VideoPlayerScreen(videoUrl: url),
      ),
    );
  }
  
  void _showError(String msg) {
    setState(() {
      _statusMessage = msg;
    });
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg), backgroundColor: Colors.red),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black, // Default black screen
      body: Stack(
        children: [
          // 1. Full-screen Image with Fade Animation
          Positioned.fill(
            child: AnimatedOpacity(
              opacity: _isScanning ? 1.0 : 0.0,
              duration: const Duration(seconds: 2),
              curve: Curves.easeIn,
              child: Image.network(
                'https://images.unsplash.com/photo-1550751827-4bd374c3f58b', // Cyberpunk/Tech background
                fit: BoxFit.cover,
                errorBuilder: (context, error, stackTrace) {
                  return Container(
                    decoration: const BoxDecoration(
                      gradient: LinearGradient(
                        begin: Alignment.topCenter,
                        end: Alignment.bottomCenter,
                        colors: [Color(0xFF2E004F), Color(0xFF000000)],
                      ),
                    ),
                  );
                },
              ),
            ),
          ),

          // 2. Scan Button & Text (Positioned at bottom for thumb reach)
          Align(
            alignment: Alignment.bottomCenter,
            child: Container(
              height: MediaQuery.of(context).size.height * 0.5,
              width: double.infinity,
              color: Colors.transparent, // Invisible touch area
              child: GestureDetector(
                behavior: HitTestBehavior.opaque,
                onTapDown: (_) => _onPressStart(),
                onTapUp: (_) => _onPressEnd(),
                onTapCancel: () => _onPressEnd(),
                child: Padding(
                  padding: const EdgeInsets.only(bottom: 80.0), // Adjust for thumb reach
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      // Status Text
                      AnimatedSwitcher(
                        duration: const Duration(milliseconds: 300),
                        child: Text(
                          _statusMessage,
                          key: ValueKey(_statusMessage),
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                            fontSize: 16,
                            color: Colors.white70,
                            letterSpacing: 1.2,
                            shadows: [Shadow(color: Colors.black, blurRadius: 4)],
                          ),
                        ),
                      ),
                      const SizedBox(height: 30),
                      
                      // Scan Icon/Button (Visual only now)
                      Stack(
                        alignment: Alignment.center,
                        children: [
                          if (_isScanning)
                            ScaleTransition(
                              scale: Tween(begin: 1.0, end: 1.5).animate(_animController),
                              child: FadeTransition(
                                opacity: Tween(begin: 0.5, end: 0.0).animate(_animController),
                                child: Container(
                                  width: 100,
                                  height: 100,
                                  decoration: BoxDecoration(
                                    shape: BoxShape.circle,
                                    border: Border.all(color: Colors.greenAccent, width: 2),
                                  ),
                                ),
                              ),
                            ),
                          Container(
                            width: 90,
                            height: 90,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              color: _isScanning ? Colors.black.withOpacity(0.8) : Colors.white.withOpacity(0.1),
                              border: Border.all(
                                color: _isScanning ? Colors.greenAccent : Colors.white.withOpacity(0.5),
                                width: 3,
                              ),
                              boxShadow: [
                                BoxShadow(
                                  color: (_isScanning ? Colors.greenAccent : Colors.purple).withOpacity(0.4),
                                  blurRadius: 20,
                                  spreadRadius: 2,
                                )
                              ],
                            ),
                            child: Icon(
                              _isScanning ? Icons.wifi_tethering : Icons.nfc,
                              size: 40,
                              color: _isScanning ? Colors.greenAccent : Colors.white,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class HistoryPage extends StatelessWidget {
  final List<String> history;
  const HistoryPage({super.key, required this.history});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("播放历史")),
      body: history.isEmpty 
        ? const Center(child: Text("暂无历史记录", style: TextStyle(color: Colors.grey)))
        : ListView.builder(
            itemCount: history.length,
            itemBuilder: (context, index) {
              return ListTile(
                leading: const Icon(Icons.movie, color: Colors.deepPurpleAccent),
                title: Text(history[index], maxLines: 1, overflow: TextOverflow.ellipsis),
                onTap: () {
                   Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (context) => VideoPlayerScreen(videoUrl: history[index]),
                    ),
                  );
                },
              );
            },
          ),
    );
  }
}

class VideoPlayerScreen extends StatefulWidget {
  final String videoUrl;
  const VideoPlayerScreen({super.key, required this.videoUrl});

  @override
  State<VideoPlayerScreen> createState() => _VideoPlayerScreenState();
}

class _VideoPlayerScreenState extends State<VideoPlayerScreen> {
  late VideoPlayerController _controller;
  bool _isInitialized = false;
  bool _showControls = true;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _initializePlayer();
  }

  Future<void> _initializePlayer() async {
    _controller = VideoPlayerController.networkUrl(Uri.parse(widget.videoUrl));
    try {
      await _controller.initialize();
      // Ensure the widget is still mounted before calling setState or playing
      if (!mounted) return;
      
      _controller.play();
      setState(() => _isInitialized = true);
      
      // Auto-hide controls after 3s
      Future.delayed(const Duration(seconds: 3), () {
        if (mounted && _controller.value.isPlaying) {
          setState(() => _showControls = false);
        }
      });
    } catch (e) {
      if (mounted) {
        setState(() => _errorMessage = '视频加载失败: $e');
      }
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: GestureDetector(
        onTap: () => setState(() => _showControls = !_showControls),
        child: Stack(
          alignment: Alignment.center,
          children: [
            if (_errorMessage != null)
              Text(_errorMessage!, style: const TextStyle(color: Colors.red)),
            
            if (_isInitialized)
              Center(
                child: AspectRatio(
                  aspectRatio: _controller.value.aspectRatio,
                  child: VideoPlayer(_controller),
                ),
              )
            else if (_errorMessage == null)
              const CircularProgressIndicator(),

            if (_showControls && _isInitialized)
              Container(
                color: Colors.black45,
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    // Top Bar
                    AppBar(
                      backgroundColor: Colors.transparent,
                      leading: const BackButton(color: Colors.white),
                    ),
                    // Center Play/Pause
                    IconButton(
                      icon: Icon(
                        _controller.value.isPlaying ? Icons.pause : Icons.play_arrow,
                        color: Colors.white, size: 60
                      ),
                      onPressed: () {
                        setState(() {
                          _controller.value.isPlaying ? _controller.pause() : _controller.play();
                        });
                      },
                    ),
                    // Bottom Bar
                    Padding(
                      padding: const EdgeInsets.all(16.0),
                      child: VideoProgressIndicator(_controller, allowScrubbing: true),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}
