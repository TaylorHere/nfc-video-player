package com.example.flutter_app

import android.app.PendingIntent
import android.content.Intent
import android.content.IntentFilter
import android.nfc.NfcAdapter
import android.nfc.tech.IsoDep
import android.nfc.tech.NfcA
import android.nfc.tech.NfcB
import android.nfc.tech.NfcF
import android.nfc.tech.NfcV
import android.os.Bundle
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity: FlutterActivity() {
    private var nfcAdapter: NfcAdapter? = null
    private var pendingIntent: PendingIntent? = null
    private var intentFilters: Array<IntentFilter>? = null
    private var techLists: Array<Array<String>>? = null
    
    // 控制是否处理 NFC 事件
    private var nfcEnabled = false
    
    private val CHANNEL = "com.example.flutter_app/nfc_control"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        
        // 设置 MethodChannel 让 Flutter 控制 NFC 状态
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL).setMethodCallHandler { call, result ->
            when (call.method) {
                "enableNfc" -> {
                    nfcEnabled = true
                    result.success(true)
                }
                "disableNfc" -> {
                    nfcEnabled = false
                    result.success(true)
                }
                "isNfcEnabled" -> {
                    result.success(nfcEnabled)
                }
                else -> {
                    result.notImplemented()
                }
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        nfcAdapter = NfcAdapter.getDefaultAdapter(this)
        
        if (nfcAdapter != null) {
            // 创建 PendingIntent，当 NFC 标签被检测到时发送给当前 Activity
            val intent = Intent(this, javaClass).apply {
                addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP)
            }
            pendingIntent = PendingIntent.getActivity(
                this, 0, intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE
            )
            
            // 设置 intent filters - 拦截所有 NFC 事件
            val ndef = IntentFilter(NfcAdapter.ACTION_NDEF_DISCOVERED)
            try {
                ndef.addDataType("*/*")
            } catch (e: IntentFilter.MalformedMimeTypeException) {
                throw RuntimeException("Failed to add MIME type.", e)
            }
            
            intentFilters = arrayOf(
                ndef,
                IntentFilter(NfcAdapter.ACTION_TAG_DISCOVERED),
                IntentFilter(NfcAdapter.ACTION_TECH_DISCOVERED)
            )
            
            // 支持的 NFC 技术类型
            techLists = arrayOf(
                arrayOf(IsoDep::class.java.name),
                arrayOf(NfcA::class.java.name),
                arrayOf(NfcB::class.java.name),
                arrayOf(NfcF::class.java.name),
                arrayOf(NfcV::class.java.name)
            )
        }
    }

    override fun onResume() {
        super.onResume()
        // App 在前台时，启用前台调度拦截所有 NFC 事件
        nfcAdapter?.enableForegroundDispatch(this, pendingIntent, intentFilters, techLists)
    }

    override fun onPause() {
        super.onPause()
        // App 进入后台时，禁用前台调度
        nfcAdapter?.disableForegroundDispatch(this)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        
        // 只有当 Flutter 端启用了 NFC 时才处理
        // 否则静默忽略（不振动，不处理）
        if (!nfcEnabled) {
            // 什么都不做，拦截事件
            return
        }
        
        // 如果启用了，让 nfc_manager 插件处理
        setIntent(intent)
    }
}
