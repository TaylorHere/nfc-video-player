import base64
import binascii
import hashlib
import hmac
import json
import posixpath
import re
import time
from urllib.parse import parse_qs, quote, unquote, urlparse

from js import Response as JsResponse
from js import Uint8Array, crypto, fetch as js_fetch
from pyodide.ffi import to_js
from workers import WorkerEntrypoint

DEFAULT_FILENAME = "butterfly.mp4"
DEFAULT_SDM_KEY_HEX = "518945027BB77671C3980890A13668E5"
TOKEN_TTL_SECONDS = 300
CDN_URL_TTL_SECONDS = 120
PLAYBACK_SESSION_TTL_SECONDS = 300
MEDIA_CACHE_SECONDS = 3600
HLS_FAIRPLAY_LICENSE_PLACEHOLDER = "__FAIRPLAY_LICENSE_URL__"
HLS_FAIRPLAY_CERTIFICATE_PLACEHOLDER = "__FAIRPLAY_CERTIFICATE_URL__"
HLS_URI_ATTR_PATTERN = re.compile(r'URI="([^"]+)"')
ADMIN_UI_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>NFC 资源浏览器</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0b1020;
      --panel: #111a33;
      --line: #263b69;
      --muted: #9fb2dd;
      --text: #e8edff;
      --ok: #86efac;
      --err: #fda4af;
      --brand: #3366ff;
      --danger: #7f1d1d;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
    }
    .wrap {
      max-width: 1280px;
      margin: 0 auto;
      padding: 18px;
    }
    .top {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: end;
      margin-bottom: 12px;
    }
    h1 { margin: 0; font-size: 24px; }
    .muted { color: var(--muted); font-size: 12px; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 12px;
    }
    .flow {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      margin-bottom: 12px;
    }
    .flow-step {
      border: 1px solid #2a3f72;
      border-radius: 10px;
      background: #0d1731;
      padding: 8px 10px;
    }
    .flow-step strong {
      display: block;
      font-size: 11px;
      color: var(--muted);
      margin-bottom: 2px;
      font-weight: 600;
      letter-spacing: .2px;
    }
    .flow-step span {
      font-size: 13px;
    }
    .flow-step.done {
      border-color: #2a7a54;
      box-shadow: inset 0 0 0 1px rgba(99, 241, 170, 0.12);
    }
    .flow-step.active {
      border-color: #4d7dff;
      box-shadow: inset 0 0 0 1px rgba(96, 143, 255, 0.25);
    }
    .ok { color: var(--ok); }
    .err { color: var(--err); white-space: pre-wrap; }
    .toolbar {
      display: grid;
      grid-template-columns: 1.2fr 1fr 1fr auto;
      gap: 8px;
      align-items: end;
      margin-bottom: 10px;
    }
    .layout {
      display: grid;
      grid-template-columns: 1.35fr 1fr;
      gap: 12px;
    }
    .section-title {
      margin: 0 0 8px;
      font-size: 15px;
    }
    .table-wrap {
      max-height: 62vh;
      overflow: auto;
      -webkit-overflow-scrolling: touch;
      border: 1px solid var(--line);
      border-radius: 8px;
    }
    .table-tip { margin: 0 0 8px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { border-bottom: 1px solid #22345a; padding: 7px 8px; text-align: left; vertical-align: top; }
    th { position: sticky; top: 0; background: #0f1831; z-index: 2; }
    tr.active { background: #1a2848; }
    .actions { display: flex; gap: 6px; flex-wrap: wrap; }
    input, textarea, button {
      width: 100%;
      border-radius: 8px;
      border: 1px solid #365080;
      background: #0e1730;
      color: var(--text);
      padding: 8px 10px;
    }
    button[disabled] {
      opacity: .55;
      cursor: not-allowed;
    }
    textarea { min-height: 94px; resize: vertical; }
    .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .grid3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
    button {
      cursor: pointer;
      background: var(--brand);
      border-color: #4a74ff;
      width: auto;
      padding: 8px 12px;
    }
    button.secondary { background: #1a2c50; }
    button.danger { background: var(--danger); border-color: #a82727; }
    .inline { display: inline-flex; align-items: center; gap: 8px; }
    .badge {
      display: inline-block;
      border: 1px solid #3f5f9b;
      border-radius: 999px;
      padding: 1px 8px;
      font-size: 11px;
      color: #bad0ff;
    }
    details.advanced {
      margin-top: 8px;
      border: 1px solid #2d4477;
      border-radius: 8px;
      padding: 8px;
      background: #0c152d;
    }
    details.advanced > summary {
      cursor: pointer;
      color: #c9d8fb;
      font-size: 12px;
      user-select: none;
    }
    .sticky-actions {
      position: sticky;
      bottom: 0;
      padding-top: 8px;
      background: linear-gradient(180deg, rgba(17,26,51,0.05) 0%, rgba(17,26,51,0.96) 35%);
    }
    #assetTable { min-width: 760px; }
    #mappingTable { min-width: 620px; }
    #assetTable td:first-child { min-width: 240px; word-break: break-all; }
    #mappingTable td:nth-child(2) { min-width: 220px; word-break: break-all; }

    @media (max-width: 980px) {
      .wrap { padding: 14px; }
      .top {
        flex-direction: column;
        align-items: flex-start;
        gap: 6px;
      }
      .toolbar { grid-template-columns: 1fr 1fr; }
      .layout { grid-template-columns: 1fr; }
      .panel { padding: 10px; }
      .flow { grid-template-columns: 1fr; }
    }

    @media (max-width: 640px) {
      .wrap { padding: 10px; }
      h1 { font-size: 20px; }
      .toolbar,
      .grid2,
      .grid3 { grid-template-columns: 1fr; }
      .actions { width: 100%; }
      .actions button {
        flex: 1 1 calc(50% - 6px);
        min-height: 40px;
      }
      input, textarea, button {
        font-size: 14px;
      }
      .inline {
        flex-wrap: wrap;
      }
      #assetTable { min-width: 680px; }
      #mappingTable { min-width: 560px; }
      .table-tip { font-size: 11px; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <div>
        <h1>NFC 资源浏览器</h1>
        <div class="muted">遵循“清晰、反馈、渐进披露”的操作流：选资源 → 设 UID → 配 DRM</div>
      </div>
      <div id="whoami" class="mono muted">加载中...</div>
    </div>

    <div class="flow" id="flowSteps">
      <div class="flow-step active" data-step="1">
        <strong>STEP 1</strong>
        <span>选择或上传资源</span>
      </div>
      <div class="flow-step" data-step="2">
        <strong>STEP 2</strong>
        <span>输入 UID 与名称</span>
      </div>
      <div class="flow-step" data-step="3">
        <strong>STEP 3</strong>
        <span>启用 DRM（可选）并保存</span>
      </div>
    </div>

    <div class="panel" style="margin-bottom:12px;">
      <div class="toolbar">
        <div>
          <label class="muted">资源前缀</label>
          <input id="prefix" placeholder="demo/" />
        </div>
        <div>
          <label class="muted">上传 key（留空自动=前缀+文件名）</label>
          <input id="uploadKey" placeholder="demo/master.m3u8" />
        </div>
        <div>
          <label class="muted">选择文件</label>
          <input type="file" id="uploadFile" />
        </div>
        <div class="actions">
          <button class="secondary" id="refreshAll">刷新</button>
          <button id="uploadBtn">上传</button>
        </div>
      </div>
      <div class="muted" id="uploadHint" style="margin-top:4px;">选择文件后会自动填充推荐 key。</div>
      <div id="assetMsg" class="mono muted"></div>
    </div>

    <div class="layout">
      <div class="panel">
        <h2 class="section-title">资源列表</h2>
        <div class="muted table-tip">手机端可左右滑动查看完整列</div>
        <div class="table-wrap">
          <table id="assetTable">
            <thead>
              <tr>
                <th>Key</th>
                <th>大小</th>
                <th>更新时间</th>
                <th>映射</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody></tbody>
          </table>
        </div>
      </div>

      <div class="panel">
        <h2 class="section-title">映射与 DRM 详情</h2>
        <div class="muted" id="selectedAssetHint">先在左侧选择资源，再配置映射。</div>
        <div class="grid2" style="margin-top:8px;">
          <div>
            <label class="muted">UID</label>
            <input id="uid" placeholder="04999911223344" />
          </div>
          <div>
            <label class="muted">名称</label>
            <input id="name" placeholder="DRM Card" />
          </div>
        </div>
        <div style="margin-top:8px;">
          <label class="muted">资源 key (filename)</label>
          <input id="filename" class="mono" placeholder="demo/master.m3u8" />
        </div>
        <div style="margin-top:8px;" class="inline">
          <input type="checkbox" id="drmEnabled" style="width:auto;" />
          <label for="drmEnabled">启用 DRM</label>
          <span class="badge">建议 HLS(.m3u8)/DASH(.mpd) 使用清单文件</span>
        </div>

        <details class="advanced" id="drmAdvanced">
          <summary>DRM 高级配置（仅启用 DRM 时填写）</summary>
          <div class="grid2" style="margin-top:8px;">
            <div>
              <label class="muted">HLS Manifest</label>
              <input id="hlsManifest" class="mono" placeholder="demo/master.m3u8" />
            </div>
            <div>
              <label class="muted">DASH Manifest</label>
              <input id="dashManifest" class="mono" placeholder="demo/master.mpd" />
            </div>
          </div>

          <div class="grid3" style="margin-top:8px;">
            <div>
              <label class="muted">Widevine License</label>
              <input id="licWidevine" placeholder="https://..." />
            </div>
            <div>
              <label class="muted">FairPlay License</label>
              <input id="licFairplay" placeholder="https://..." />
            </div>
            <div>
              <label class="muted">PlayReady License</label>
              <input id="licPlayready" placeholder="https://..." />
            </div>
          </div>

          <div class="grid3" style="margin-top:8px;">
            <div>
              <label class="muted">Widevine Cert</label>
              <input id="certWidevine" placeholder="https://..." />
            </div>
            <div>
              <label class="muted">FairPlay Cert</label>
              <input id="certFairplay" placeholder="https://..." />
            </div>
            <div>
              <label class="muted">PlayReady Cert</label>
              <input id="certPlayready" placeholder="https://..." />
            </div>
          </div>

          <div style="margin-top:8px;">
            <label class="muted">DRM Header JSON（可选，格式: {"widevine":{"x-token":"..."}}）</label>
            <textarea id="drmHeaders" class="mono" placeholder="{}"></textarea>
          </div>
        </details>

        <div class="sticky-actions">
          <div class="actions" style="margin-top:8px;">
            <button id="saveMapping">保存映射</button>
            <button class="secondary" id="loadMappingByUid">按 UID 加载</button>
            <button class="secondary" id="clearForm">清空表单</button>
            <button class="danger" id="deleteMappingByUid">删除 UID 映射</button>
          </div>
          <div id="mappingMsg" class="mono muted" style="margin-top:8px;"></div>
        </div>

        <div style="margin-top:12px;">
          <h3 class="section-title">映射列表</h3>
          <div class="muted table-tip">手机端可左右滑动查看完整列</div>
          <div class="table-wrap" style="max-height:220px;">
            <table id="mappingTable">
              <thead><tr><th>UID</th><th>filename</th><th>DRM</th><th>操作</th></tr></thead>
              <tbody></tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script>
    const apiBase = "/admin/api";
    const state = {
      assets: [],
      mappings: [],
      mappingByUid: new Map(),
      mappingsByFile: new Map(),
      selectedKey: "",
      dirty: false
    };
    const FORM_FIELDS = [
      "uid", "name", "filename", "drmEnabled",
      "hlsManifest", "dashManifest",
      "licWidevine", "licFairplay", "licPlayready",
      "certWidevine", "certFairplay", "certPlayready",
      "drmHeaders"
    ];

    function esc(v) {
      return String(v ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
    }

    function setMsg(id, text, ok = true) {
      const el = document.getElementById(id);
      el.className = ok ? "mono ok" : "mono err";
      el.textContent = text || "";
    }

    async function api(path, options = {}) {
      const res = await fetch(apiBase + path, options);
      const text = await res.text();
      let data = null;
      try { data = text ? JSON.parse(text) : null; } catch (_) {}
      if (!res.ok) {
        const message = (data && (data.error || data.message)) ? (data.error || data.message) : text;
        throw new Error(message || ("HTTP " + res.status));
      }
      return data;
    }

    function cleanObject(obj) {
      const out = {};
      Object.entries(obj || {}).forEach(([k, v]) => {
        if (v === null || v === undefined) return;
        if (typeof v === "string" && !v.trim()) return;
        if (typeof v === "object" && !Array.isArray(v) && Object.keys(v).length === 0) return;
        out[k] = v;
      });
      return out;
    }

    function normalizePrefix(raw) {
      let value = String(raw || "").trim();
      while (value.startsWith("/")) value = value.slice(1);
      while (value.endsWith("/")) value = value.slice(0, -1);
      return value;
    }

    function toMapByFile(mappings) {
      const map = new Map();
      (mappings || []).forEach((item) => {
        const key = String(item.filename || "").trim();
        if (!key) return;
        const list = map.get(key) || [];
        list.push(item);
        map.set(key, list);
      });
      return map;
    }

    function fmtBytes(bytes) {
      const n = Number(bytes || 0);
      if (!Number.isFinite(n) || n < 1024) return String(n || 0);
      if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
      if (n < 1024 * 1024 * 1024) return (n / (1024 * 1024)).toFixed(1) + " MB";
      return (n / (1024 * 1024 * 1024)).toFixed(1) + " GB";
    }

    function updateFlow() {
      const hasAsset = !!(state.selectedKey || document.getElementById("filename").value.trim());
      const hasUid = !!document.getElementById("uid").value.trim();
      const drmEnabled = !!document.getElementById("drmEnabled").checked;
      const hasManifest = !!(
        document.getElementById("hlsManifest").value.trim()
        || document.getElementById("dashManifest").value.trim()
      );

      const steps = [
        { key: "1", done: hasAsset, active: !hasAsset },
        { key: "2", done: hasUid, active: hasAsset && !hasUid },
        { key: "3", done: (!drmEnabled || hasManifest) && hasUid, active: hasAsset && hasUid && drmEnabled && !hasManifest }
      ];
      steps.forEach((step) => {
        const node = document.querySelector(".flow-step[data-step='" + step.key + "']");
        if (!node) return;
        node.classList.toggle("done", !!step.done);
        node.classList.toggle("active", !!step.active);
      });

      const saveBtn = document.getElementById("saveMapping");
      if (saveBtn) {
        saveBtn.disabled = !(hasAsset && hasUid && (!drmEnabled || hasManifest));
      }
    }

    function markDirty() {
      state.dirty = true;
      updateFlow();
    }

    function clearDirty() {
      state.dirty = false;
      updateFlow();
    }

    function suggestUploadKeyFromFile() {
      const keyInput = document.getElementById("uploadKey");
      const fileEl = document.getElementById("uploadFile");
      const file = fileEl.files && fileEl.files[0];
      if (!file) {
        document.getElementById("uploadHint").textContent = "选择文件后会自动填充推荐 key。";
        return;
      }
      if (keyInput.value.trim()) {
        document.getElementById("uploadHint").textContent = "已手动填写 key，上传时将优先使用手动值。";
        return;
      }
      const prefix = normalizePrefix(document.getElementById("prefix").value);
      const fileName = String(file.name || "").replace(/^\/+/, "");
      keyInput.value = prefix ? (prefix + "/" + fileName) : fileName;
      document.getElementById("uploadHint").textContent = "推荐 key 已填充，可直接上传。";
    }

    function clearMappingForm() {
      [
        "uid", "name", "filename", "hlsManifest", "dashManifest",
        "licWidevine", "licFairplay", "licPlayready",
        "certWidevine", "certFairplay", "certPlayready"
      ].forEach((id) => { document.getElementById(id).value = ""; });
      document.getElementById("drmEnabled").checked = false;
      document.getElementById("drmAdvanced").open = false;
      document.getElementById("drmHeaders").value = "{}";
      clearDirty();
    }

    function fillFormFromMapping(mapping) {
      if (!mapping) return;
      const drm = mapping.drm || {};
      const licenses = drm.licenses || {};
      const certs = drm.certificates || {};
      const headers = drm.headers || {};
      document.getElementById("uid").value = mapping.uid || "";
      document.getElementById("name").value = mapping.name || "";
      document.getElementById("filename").value = mapping.filename || "";
      document.getElementById("drmEnabled").checked = !!drm.enabled;
      document.getElementById("hlsManifest").value = drm.hls_manifest || "";
      document.getElementById("dashManifest").value = drm.dash_manifest || "";
      document.getElementById("licWidevine").value = licenses.widevine || "";
      document.getElementById("licFairplay").value = licenses.fairplay || "";
      document.getElementById("licPlayready").value = licenses.playready || "";
      document.getElementById("certWidevine").value = certs.widevine || "";
      document.getElementById("certFairplay").value = certs.fairplay || "";
      document.getElementById("certPlayready").value = certs.playready || "";
      document.getElementById("drmHeaders").value = JSON.stringify(headers || {}, null, 2);
      document.getElementById("drmAdvanced").open = !!drm.enabled;
      applySelectedAsset(mapping.filename || "", true);
      clearDirty();
    }

    function formToDrmConfig() {
      const enabled = document.getElementById("drmEnabled").checked;
      let headers = {};
      const headersRaw = document.getElementById("drmHeaders").value.trim();
      if (headersRaw) {
        headers = JSON.parse(headersRaw);
      }
      return cleanObject({
        enabled,
        hls_manifest: document.getElementById("hlsManifest").value.trim(),
        dash_manifest: document.getElementById("dashManifest").value.trim(),
        licenses: cleanObject({
          widevine: document.getElementById("licWidevine").value.trim(),
          fairplay: document.getElementById("licFairplay").value.trim(),
          playready: document.getElementById("licPlayready").value.trim()
        }),
        certificates: cleanObject({
          widevine: document.getElementById("certWidevine").value.trim(),
          fairplay: document.getElementById("certFairplay").value.trim(),
          playready: document.getElementById("certPlayready").value.trim()
        }),
        headers: cleanObject(headers)
      });
    }

    function applySelectedAsset(key, force = false) {
      const normalized = key || "";
      if (!force && state.dirty && normalized !== state.selectedKey) {
        const proceed = confirm("当前有未保存修改，切换资源可能覆盖 filename。是否继续？");
        if (!proceed) return;
      }
      state.selectedKey = key || "";
      if (key) {
        document.getElementById("filename").value = key;
        if (key.endsWith(".m3u8") && !document.getElementById("hlsManifest").value.trim()) {
          document.getElementById("hlsManifest").value = key;
        }
        if (key.endsWith(".mpd") && !document.getElementById("dashManifest").value.trim()) {
          document.getElementById("dashManifest").value = key;
        }
      }
      const mapped = state.mappingsByFile.get(key) || [];
      const hint = mapped.length
        ? ("当前资源已映射 UID: " + mapped.map((m) => m.uid).join(", "))
        : "当前资源尚未被映射";
      document.getElementById("selectedAssetHint").textContent = key ? ("已选资源: " + key + " | " + hint) : "先在左侧选择资源，再配置映射。";
      renderAssets();
      updateFlow();
    }

    function renderMappings() {
      const tbody = document.querySelector("#mappingTable tbody");
      tbody.innerHTML = state.mappings.map((row) => {
        const drm = row.drm && row.drm.enabled ? "enabled" : "disabled";
        return "<tr>"
          + "<td class='mono'>" + esc(row.uid) + "</td>"
          + "<td class='mono'>" + esc(row.filename) + "</td>"
          + "<td>" + drm + "</td>"
          + "<td class='actions'>"
          + "<button class='secondary' data-action='use-mapping' data-uid='" + esc(row.uid) + "'>编辑</button>"
          + "<button class='danger' data-action='del-mapping' data-uid='" + esc(row.uid) + "'>删除</button>"
          + "</td>"
          + "</tr>";
      }).join("");
    }

    function renderAssets() {
      const tbody = document.querySelector("#assetTable tbody");
      tbody.innerHTML = state.assets.map((row) => {
        const mapped = state.mappingsByFile.get(row.key) || [];
        const mappedHint = mapped.length ? (mapped.length + " 个") : "-";
        const drmHint = mapped.some((m) => m.drm && m.drm.enabled) ? "DRM" : "";
        const activeClass = row.key === state.selectedKey ? " class='active'" : "";
        return "<tr" + activeClass + ">"
          + "<td class='mono'>" + esc(row.key) + (drmHint ? " <span class='badge'>" + drmHint + "</span>" : "") + "</td>"
          + "<td>" + esc(fmtBytes(row.size)) + "</td>"
          + "<td>" + esc(row.uploaded || "") + "</td>"
          + "<td>" + esc(mappedHint) + "</td>"
          + "<td class='actions'>"
          + "<button class='secondary' data-action='pick' data-key='" + esc(row.key) + "'>选择</button>"
          + "<button class='secondary' data-action='map' data-key='" + esc(row.key) + "'>映射</button>"
          + "<button class='secondary' data-action='download' data-key='" + esc(row.key) + "'>下载</button>"
          + "<button class='danger' data-action='delete' data-key='" + esc(row.key) + "'>删除</button>"
          + "</td>"
          + "</tr>";
      }).join("");
    }

    async function loadMe() {
      try {
        const data = await api("/me");
        document.getElementById("whoami").textContent = "已登录: " + (data.email || "unknown") + " (" + (data.auth || "unknown") + ")";
      } catch (e) {
        document.getElementById("whoami").textContent = "鉴权失败: " + e.message;
      }
    }

    async function loadMappings() {
      const data = await api("/mappings");
      state.mappings = Array.isArray(data.items) ? data.items : [];
      state.mappingByUid = new Map(state.mappings.map((item) => [String(item.uid || "").toUpperCase(), item]));
      state.mappingsByFile = toMapByFile(state.mappings);
      renderMappings();
    }

    async function loadAssets() {
      const prefix = document.getElementById("prefix").value.trim();
      const data = await api("/assets" + (prefix ? ("?prefix=" + encodeURIComponent(prefix)) : ""));
      state.assets = Array.isArray(data.items) ? data.items : [];
      renderAssets();
    }

    async function refreshAll() {
      try {
        setMsg("assetMsg", "正在同步资源与映射...", true);
        await Promise.all([loadMe(), loadMappings(), loadAssets()]);
        setMsg("assetMsg", "同步完成", true);
        updateFlow();
      } catch (e) {
        setMsg("assetMsg", "刷新失败: " + e.message, false);
      }
    }

    async function uploadAsset() {
      const fileEl = document.getElementById("uploadFile");
      const file = fileEl.files && fileEl.files[0];
      if (!file) {
        setMsg("assetMsg", "请选择上传文件", false);
        return;
      }
      suggestUploadKeyFromFile();
      const key = document.getElementById("uploadKey").value.trim();
      if (!key) {
        setMsg("assetMsg", "请填写 key", false);
        return;
      }
      try {
        await api("/assets/upload?key=" + encodeURIComponent(key), {
          method: "POST",
          headers: {
            "content-type": file.type || "application/octet-stream",
            "x-upload-content-type": file.type || "application/octet-stream"
          },
          body: file
        });
        setMsg("assetMsg", "上传成功: " + key, true);
        document.getElementById("uploadKey").value = "";
        fileEl.value = "";
        await loadAssets();
      } catch (e) {
        setMsg("assetMsg", "上传失败: " + e.message, false);
      }
    }

    async function saveMapping() {
      const uid = document.getElementById("uid").value.trim().toUpperCase();
      const filename = document.getElementById("filename").value.trim();
      const name = document.getElementById("name").value.trim();
      if (!uid || !filename) {
        setMsg("mappingMsg", "UID 和 filename 必填", false);
        return;
      }
      let drm;
      try {
        drm = formToDrmConfig();
        if (drm.enabled && !(drm.hls_manifest || drm.dash_manifest)) {
          setMsg("mappingMsg", "启用 DRM 时请至少填写 HLS 或 DASH 清单路径", false);
          return;
        }
      } catch (e) {
        setMsg("mappingMsg", "DRM Header JSON 解析失败: " + e.message, false);
        return;
      }
      const payload = { uid, filename, drm };
      if (name) payload.name = name;
      try {
        await api("/mappings", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(payload)
        });
        setMsg("mappingMsg", "保存成功", true);
        clearDirty();
        applySelectedAsset(filename, true);
        await loadMappings();
        renderAssets();
      } catch (e) {
        setMsg("mappingMsg", "保存失败: " + e.message, false);
      }
    }

    async function loadMappingByUid() {
      const uid = document.getElementById("uid").value.trim().toUpperCase();
      if (!uid) {
        setMsg("mappingMsg", "请先输入 UID", false);
        return;
      }
      let mapping = state.mappingByUid.get(uid);
      if (!mapping) {
        try {
          const data = await api("/mappings/" + encodeURIComponent(uid));
          mapping = data.item || null;
        } catch (_) {
          mapping = null;
        }
      }
      if (!mapping) {
        setMsg("mappingMsg", "未找到 UID 映射: " + uid, false);
        return;
      }
      fillFormFromMapping(mapping);
      setMsg("mappingMsg", "已加载 UID: " + uid, true);
    }

    async function deleteMappingByUid() {
      const uid = document.getElementById("uid").value.trim().toUpperCase();
      if (!uid) {
        setMsg("mappingMsg", "请先输入 UID", false);
        return;
      }
      if (!confirm("确认删除映射 " + uid + " ?")) return;
      try {
        await api("/mappings/" + encodeURIComponent(uid), { method: "DELETE" });
        setMsg("mappingMsg", "已删除: " + uid, true);
        if (document.getElementById("uid").value.trim().toUpperCase() === uid) {
          clearMappingForm();
          if (state.selectedKey) {
            document.getElementById("filename").value = state.selectedKey;
          }
        }
        await loadMappings();
        renderAssets();
      } catch (e) {
        setMsg("mappingMsg", "删除失败: " + e.message, false);
      }
    }

    async function downloadAsset(key) {
      try {
        const data = await api("/assets/sign?key=" + encodeURIComponent(key));
        if (!data || !data.url) throw new Error("未返回下载地址");
        window.open(data.url, "_blank", "noopener");
      } catch (e) {
        setMsg("assetMsg", "下载地址生成失败: " + e.message, false);
      }
    }

    async function deleteAsset(key) {
      if (!confirm("确认删除资源 " + key + " ?")) return;
      try {
        await api("/assets/" + encodeURIComponent(key), { method: "DELETE" });
        setMsg("assetMsg", "已删除: " + key, true);
        if (state.selectedKey === key) {
          state.selectedKey = "";
          document.getElementById("selectedAssetHint").textContent = "先在左侧选择资源，再配置映射。";
          updateFlow();
        }
        await loadAssets();
      } catch (e) {
        setMsg("assetMsg", "删除失败: " + e.message, false);
      }
    }

    document.getElementById("assetTable").addEventListener("click", async (evt) => {
      const btn = evt.target.closest("button[data-action]");
      if (!btn) return;
      const action = btn.getAttribute("data-action");
      const key = btn.getAttribute("data-key");
      if (action === "pick") {
        applySelectedAsset(key);
        return;
      }
      if (action === "map") {
        applySelectedAsset(key);
        document.getElementById("filename").value = key || "";
        return;
      }
      if (action === "download") {
        await downloadAsset(key);
        return;
      }
      if (action === "delete") {
        await deleteAsset(key);
      }
    });

    document.getElementById("mappingTable").addEventListener("click", async (evt) => {
      const btn = evt.target.closest("button[data-action]");
      if (!btn) return;
      const action = btn.getAttribute("data-action");
      const uid = (btn.getAttribute("data-uid") || "").toUpperCase();
      if (!uid) return;
      if (action === "use-mapping") {
        const mapping = state.mappingByUid.get(uid);
        if (mapping) {
          fillFormFromMapping(mapping);
          setMsg("mappingMsg", "已载入映射: " + uid, true);
        }
        return;
      }
      if (action === "del-mapping") {
        document.getElementById("uid").value = uid;
        await deleteMappingByUid();
      }
    });

    document.getElementById("uploadFile").addEventListener("change", suggestUploadKeyFromFile);
    document.getElementById("uploadKey").addEventListener("input", () => {
      const raw = document.getElementById("uploadKey").value.trim();
      document.getElementById("uploadHint").textContent = raw
        ? "将使用手动 key 上传。"
        : "选择文件后会自动填充推荐 key。";
    });
    document.getElementById("prefix").addEventListener("change", () => {
      suggestUploadKeyFromFile();
      loadAssets().catch((e) => setMsg("assetMsg", "加载资源失败: " + e.message, false));
    });
    document.getElementById("refreshAll").onclick = refreshAll;
    document.getElementById("uploadBtn").onclick = uploadAsset;
    document.getElementById("saveMapping").onclick = saveMapping;
    document.getElementById("loadMappingByUid").onclick = loadMappingByUid;
    document.getElementById("deleteMappingByUid").onclick = deleteMappingByUid;
    document.getElementById("clearForm").onclick = () => {
      if (state.dirty) {
        const proceed = confirm("确认清空当前未保存内容？");
        if (!proceed) return;
      }
      clearMappingForm();
      if (state.selectedKey) {
        document.getElementById("filename").value = state.selectedKey;
      }
      updateFlow();
    };

    FORM_FIELDS.forEach((id) => {
      const el = document.getElementById(id);
      if (!el) return;
      const eventName = (el.type === "checkbox") ? "change" : "input";
      el.addEventListener(eventName, () => {
        markDirty();
      });
    });
    document.getElementById("drmEnabled").addEventListener("change", () => {
      document.getElementById("drmAdvanced").open = !!document.getElementById("drmEnabled").checked;
      updateFlow();
    });

    clearMappingForm();
    refreshAll();
    updateFlow();
  </script>
</body>
</html>
"""


def _json_response(payload: dict | list, status: int = 200):
    return JsResponse.new(
        json.dumps(payload),
        to_js(
            {
                "status": status,
                "headers": {
                    "content-type": "application/json; charset=utf-8",
                    "cache-control": "no-store",
                },
            }
        ),
    )


def _text_response(message: str, status: int = 200):
    return JsResponse.new(
        message,
        to_js(
            {
                "status": status,
                "headers": {
                    "content-type": "text/plain; charset=utf-8",
                    "cache-control": "no-store",
                },
            }
        ),
    )


def _cors_headers() -> dict:
    return {
        "access-control-allow-origin": "*",
        "access-control-allow-methods": "GET,HEAD,POST,DELETE,OPTIONS",
        "access-control-allow-headers": "*",
        "access-control-expose-headers": "*",
        "cache-control": "no-store",
    }


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def _is_absolute_http_url(value: str) -> bool:
    lower = value.lower()
    return lower.startswith("http://") or lower.startswith("https://")


def _clamp_int(raw_value, min_value: int, max_value: int, default_value: int) -> int:
    try:
        value = int(str(raw_value))
    except Exception:
        value = default_value
    return max(min_value, min(value, max_value))


def _js_to_py(value):
    if hasattr(value, "to_py"):
        return value.to_py()
    return value


def _field(row, key: str, default=None):
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def _safe_object_key(path_value: str) -> str:
    raw = unquote(str(path_value or "")).strip()
    if not raw:
        raise ValueError("invalid object key")
    if any(ch in raw for ch in ("\x00", "\n", "\r")):
        raise ValueError("invalid object key")

    raw = raw.lstrip("/")
    parts = raw.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("invalid object key")

    normalized = posixpath.normpath(raw)
    if normalized in ("", ".", "/") or normalized.startswith("../"):
        raise ValueError("invalid object key")
    return normalized


def _normalize_media_key(raw_filename: str) -> str:
    filename = str(raw_filename or "").strip()
    if _is_absolute_http_url(filename):
        filename = urlparse(filename).path
    return _safe_object_key(filename)


def _relative_key(base_dir: str, relative_uri: str) -> str:
    if relative_uri.startswith("/"):
        return _safe_object_key(relative_uri)
    if base_dir:
        joined = posixpath.join(base_dir, relative_uri)
    else:
        joined = relative_uri
    return _safe_object_key(posixpath.normpath(joined))


def _normalize_string_dict(raw_value) -> dict[str, str]:
    if not isinstance(raw_value, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, value in raw_value.items():
        if key is None or value is None:
            continue
        header_name = str(key).strip()
        header_value = str(value).strip()
        if not header_name:
            continue
        normalized[header_name] = header_value
    return normalized


async def _decrypt_sun_payload(p_hex: str, key: bytes) -> bytes:
    encrypted = binascii.unhexlify(p_hex)
    if not encrypted or len(encrypted) % 16 != 0:
        raise ValueError("Invalid p payload length")

    key_u8 = Uint8Array.new(len(key))
    for index, value in enumerate(key):
        key_u8[index] = value

    enc_u8 = Uint8Array.new(len(encrypted))
    for index, value in enumerate(encrypted):
        enc_u8[index] = value

    iv_u8 = Uint8Array.new(16)
    crypto_key = await crypto.subtle.importKey(
        "raw",
        key_u8,
        to_js({"name": "AES-CBC"}),
        False,
        to_js(["decrypt"]),
    )
    decrypted_buffer = await crypto.subtle.decrypt(
        to_js({"name": "AES-CBC", "iv": iv_u8}),
        crypto_key,
        enc_u8,
    )
    decrypted_u8 = Uint8Array.new(decrypted_buffer)
    try:
        return bytes(decrypted_u8.to_py())
    except Exception:
        return bytes(int(decrypted_u8[i]) for i in range(decrypted_u8.length))


class Default(WorkerEntrypoint):
    def _token_secret(self) -> bytes:
        secret = getattr(self.env, "TOKEN_SECRET", None)
        if not secret:
            secret = "dev-token-secret-change-me"
        return str(secret).encode("utf-8")

    def _cdn_secret(self) -> bytes:
        secret = getattr(self.env, "CDN_SIGN_SECRET", None)
        if secret:
            return str(secret).encode("utf-8")
        return self._token_secret()

    def _playback_secret(self) -> bytes:
        secret = getattr(self.env, "PLAYBACK_SIGN_SECRET", None)
        if secret:
            return str(secret).encode("utf-8")
        return self._cdn_secret()

    def _token_ttl_seconds(self) -> int:
        return _clamp_int(
            getattr(self.env, "TOKEN_TTL_SECONDS", TOKEN_TTL_SECONDS),
            30,
            3600,
            TOKEN_TTL_SECONDS,
        )

    def _cdn_ttl_seconds(self) -> int:
        return _clamp_int(
            getattr(self.env, "CDN_URL_TTL_SECONDS", CDN_URL_TTL_SECONDS),
            30,
            3600,
            CDN_URL_TTL_SECONDS,
        )

    def _playback_ttl_seconds(self) -> int:
        return _clamp_int(
            getattr(self.env, "PLAYBACK_SESSION_TTL_SECONDS", PLAYBACK_SESSION_TTL_SECONDS),
            60,
            7200,
            PLAYBACK_SESSION_TTL_SECONDS,
        )

    @staticmethod
    def _hmac_sha256(secret: bytes, payload: bytes) -> bytes:
        return hmac.new(secret, payload, hashlib.sha256).digest()

    def _issue_signed_payload(self, payload: dict, secret: bytes) -> str:
        payload_raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )
        signature = self._hmac_sha256(secret, payload_raw)
        return f"{_b64url_encode(payload_raw)}.{_b64url_encode(signature)}"

    def _validate_signed_payload(self, token: str, secret: bytes) -> dict | None:
        try:
            payload_part, signature_part = token.split(".", 1)
            payload_raw = _b64url_decode(payload_part)
            signature_raw = _b64url_decode(signature_part)
        except Exception:
            return None

        expected = self._hmac_sha256(secret, payload_raw)
        if not hmac.compare_digest(signature_raw, expected):
            return None

        try:
            payload = json.loads(payload_raw.decode("utf-8"))
        except Exception:
            return None

        expires_at = int(payload.get("exp", 0))
        if int(time.time()) > expires_at:
            return None
        return payload

    def _issue_token(self, uid: str, filename: str) -> str:
        payload = {
            "uid": uid,
            "filename": filename,
            "exp": int(time.time()) + self._token_ttl_seconds(),
        }
        return self._issue_signed_payload(payload, self._token_secret())

    def _validate_token(self, token: str) -> dict | None:
        return self._validate_signed_payload(token, self._token_secret())

    def _cdn_signature(self, object_key: str, expires_at: int) -> str:
        payload = f"{object_key}\n{expires_at}".encode("utf-8")
        signature = self._hmac_sha256(self._cdn_secret(), payload)
        return _b64url_encode(signature)

    def _issue_cdn_url(self, origin: str, object_key: str) -> str:
        expires_at = int(time.time()) + self._cdn_ttl_seconds()
        signature = self._cdn_signature(object_key, expires_at)
        encoded_key = quote(object_key, safe="/")
        return f"{origin}/cdn/{encoded_key}?exp={expires_at}&sig={signature}"

    def _validate_cdn_url(self, object_key: str, exp_raw: str, sig_raw: str) -> bool:
        try:
            expires_at = int(exp_raw)
        except Exception:
            return False

        if int(time.time()) > expires_at:
            return False

        expected = self._cdn_signature(object_key, expires_at)
        return hmac.compare_digest(sig_raw, expected)

    def _default_drm_config(self) -> dict:
        return {
            "enabled": False,
            "hls_manifest": None,
            "dash_manifest": None,
            "licenses": {},
            "certificates": {},
            "headers": {},
        }

    def _normalize_drm_config(self, drm_payload) -> dict:
        if not isinstance(drm_payload, dict):
            return self._default_drm_config()

        config = self._default_drm_config()
        hls_manifest = drm_payload.get("hls_manifest")
        dash_manifest = drm_payload.get("dash_manifest")
        if hls_manifest:
            config["hls_manifest"] = _normalize_media_key(str(hls_manifest))
        if dash_manifest:
            config["dash_manifest"] = _normalize_media_key(str(dash_manifest))

        licenses: dict[str, str] = {}
        raw_licenses = drm_payload.get("licenses")
        if isinstance(raw_licenses, dict):
            for drm_type in ("widevine", "fairplay", "playready"):
                value = raw_licenses.get(drm_type)
                if value:
                    value = str(value).strip()
                    if not _is_absolute_http_url(value):
                        raise ValueError(f"drm license url must be absolute: {drm_type}")
                    licenses[drm_type] = value

        legacy_license_map = {
            "widevine_license_url": "widevine",
            "fairplay_license_url": "fairplay",
            "playready_license_url": "playready",
        }
        for legacy_key, drm_type in legacy_license_map.items():
            value = drm_payload.get(legacy_key)
            if value:
                value = str(value).strip()
                if not _is_absolute_http_url(value):
                    raise ValueError(f"drm license url must be absolute: {drm_type}")
                licenses[drm_type] = value

        certificates: dict[str, str] = {}
        raw_certificates = drm_payload.get("certificates")
        if isinstance(raw_certificates, dict):
            for drm_type in ("widevine", "fairplay", "playready"):
                value = raw_certificates.get(drm_type)
                if not value:
                    continue
                value = str(value).strip()
                if not _is_absolute_http_url(value):
                    raise ValueError(f"drm certificate url must be absolute: {drm_type}")
                certificates[drm_type] = value

        legacy_certificate_map = {
            "widevine_certificate_url": "widevine",
            "fairplay_certificate_url": "fairplay",
            "playready_certificate_url": "playready",
        }
        for legacy_key, drm_type in legacy_certificate_map.items():
            value = drm_payload.get(legacy_key)
            if not value:
                continue
            value = str(value).strip()
            if not _is_absolute_http_url(value):
                raise ValueError(f"drm certificate url must be absolute: {drm_type}")
            certificates[drm_type] = value

        headers: dict[str, dict[str, str]] = {}
        raw_headers = drm_payload.get("headers")
        if isinstance(raw_headers, dict):
            for drm_type in ("widevine", "fairplay", "playready"):
                header_map = _normalize_string_dict(raw_headers.get(drm_type))
                if header_map:
                    headers[drm_type] = header_map

        raw_legacy_headers = drm_payload.get("license_headers")
        if isinstance(raw_legacy_headers, dict):
            for drm_type in ("widevine", "fairplay", "playready"):
                header_map = _normalize_string_dict(raw_legacy_headers.get(drm_type))
                if header_map:
                    headers[drm_type] = header_map

        config["licenses"] = licenses
        config["certificates"] = certificates
        config["headers"] = headers
        enabled_flag = drm_payload.get("enabled")
        if enabled_flag is None:
            enabled = bool(config["hls_manifest"] or config["dash_manifest"])
        else:
            enabled = bool(enabled_flag)

        if enabled and not (config["hls_manifest"] or config["dash_manifest"]):
            raise ValueError("drm enabled requires hls_manifest or dash_manifest")

        config["enabled"] = enabled
        return config

    async def _ensure_schema(self):
        if getattr(self, "_schema_ready", False):
            return

        await self.env.DB.prepare(
            """
            CREATE TABLE IF NOT EXISTS mappings (
                uid TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                name TEXT,
                drm_config TEXT,
                updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
            )
            """
        ).run()

        # Migrate older table definitions without drm_config.
        pragma_result = await self.env.DB.prepare("PRAGMA table_info(mappings)").all()
        columns = _js_to_py(pragma_result.results) or []
        column_names = {str(_field(column, "name", "")) for column in columns}
        if "drm_config" not in column_names:
            try:
                await self.env.DB.prepare("ALTER TABLE mappings ADD COLUMN drm_config TEXT").run()
            except Exception:
                pass

        self._schema_ready = True

    def _html_response(self, html: str, status: int = 200):
        return JsResponse.new(
            html,
            to_js(
                {
                    "status": status,
                    "headers": {
                        "content-type": "text/html; charset=utf-8",
                        "cache-control": "no-store",
                    },
                }
            ),
        )

    def _admin_allowlist(self) -> set[str]:
        raw = str(getattr(self.env, "ADMIN_EMAIL_ALLOWLIST", "") or "").strip()
        if not raw:
            return set()
        return {item.strip().lower() for item in raw.split(",") if item.strip()}

    def _extract_bearer_token(self, request) -> str | None:
        auth_header = request.headers.get("authorization")
        if not auth_header:
            return None
        auth_header = str(auth_header).strip()
        if not auth_header.lower().startswith("bearer "):
            return None
        token = auth_header[7:].strip()
        return token or None

    def _authorize_admin(self, request):
        api_token = str(getattr(self.env, "ADMIN_API_TOKEN", "") or "").strip()
        bearer_token = self._extract_bearer_token(request)
        if api_token and bearer_token and hmac.compare_digest(bearer_token, api_token):
            return {"auth": "api_token", "email": "api-token"}

        email = (
            request.headers.get("CF-Access-Authenticated-User-Email")
            or request.headers.get("Cf-Access-Authenticated-User-Email")
            or request.headers.get("cf-access-authenticated-user-email")
        )
        if not email:
            return None

        email = str(email).strip().lower()
        if not email:
            return None

        allowlist = self._admin_allowlist()
        if allowlist and email not in allowlist:
            return {"error": "forbidden_email", "email": email}

        return {"auth": "cloudflare_access", "email": email}

    def _admin_unauthorized_response(self):
        return _json_response(
            {
                "error": "admin authorization required",
                "hint": "Protect /admin with Cloudflare Access and pass CF-Access-Authenticated-User-Email header",
            },
            status=401,
        )

    def _admin_forbidden_response(self):
        return _json_response(
            {
                "error": "forbidden",
                "hint": "Your email is not in ADMIN_EMAIL_ALLOWLIST",
            },
            status=403,
        )

    async def _read_binary_body(self, obj):
        # Runtime API naming differs between Worker Python versions.
        for name in ("arrayBuffer", "array_buffer"):
            method = getattr(obj, name, None)
            if callable(method):
                return await method()

        # Fallback: read text and encode.
        text_method = getattr(obj, "text", None)
        if callable(text_method):
            text_value = await text_method()
            return str(text_value).encode("utf-8")

        raise AttributeError("No supported binary body reader on object")

    async def _read_text_body(self, obj) -> str:
        text_method = getattr(obj, "text", None)
        if callable(text_method):
            value = await text_method()
            return str(value)
        body = await self._read_binary_body(obj)
        if isinstance(body, (bytes, bytearray, memoryview)):
            return bytes(body).decode("utf-8", errors="replace")
        if hasattr(body, "to_py"):
            try:
                py_body = body.to_py()
                if isinstance(py_body, (bytes, bytearray, memoryview)):
                    return bytes(py_body).decode("utf-8", errors="replace")
            except Exception:
                pass
        return str(body)

    def _to_uint8_array(self, raw: bytes):
        data = bytes(raw)
        arr = Uint8Array.new(len(data))
        for index, value in enumerate(data):
            arr[index] = value
        return arr

    def _coerce_js_body(self, body):
        if body is None:
            return body
        if isinstance(body, str):
            return body
        if isinstance(body, (bytes, bytearray, memoryview)):
            return self._to_uint8_array(bytes(body))
        if isinstance(body, (list, tuple)):
            try:
                return self._to_uint8_array(bytes(int(v) & 0xFF for v in body))
            except Exception:
                return body

        # JS ArrayBuffer / ReadableStream / TypedArray will pass through.
        if hasattr(body, "byteLength") or hasattr(body, "getReader"):
            return body

        if hasattr(body, "to_py"):
            try:
                py_value = body.to_py()
                if isinstance(py_value, (bytes, bytearray, memoryview)):
                    return self._to_uint8_array(bytes(py_value))
                if isinstance(py_value, (list, tuple)):
                    return self._to_uint8_array(bytes(int(v) & 0xFF for v in py_value))
            except Exception:
                pass

        return body

    def _estimate_body_size(self, body) -> int:
        if body is None:
            return 0
        if isinstance(body, str):
            return len(body.encode("utf-8"))
        if isinstance(body, (bytes, bytearray, memoryview)):
            return len(body)
        if hasattr(body, "byteLength"):
            try:
                return int(getattr(body, "byteLength"))
            except Exception:
                return 0
        return 0

    async def _upsert_mapping(
        self, uid: str, filename: str, name: str | None, drm_config: dict | None
    ) -> dict:
        uid_normalized = uid.upper()
        drm_json = json.dumps(drm_config, separators=(",", ":"), sort_keys=True)
        await self.env.DB.prepare(
            """
            INSERT INTO mappings (uid, filename, name, drm_config, updated_at)
            VALUES (?, ?, ?, ?, strftime('%s', 'now'))
            ON CONFLICT(uid) DO UPDATE SET
                filename = excluded.filename,
                name = excluded.name,
                drm_config = excluded.drm_config,
                updated_at = strftime('%s', 'now')
            """
        ).bind(uid_normalized, filename, name, drm_json).run()
        return {
            "uid": uid_normalized,
            "filename": filename,
            "name": name,
            "drm": drm_config or self._default_drm_config(),
        }

    async def _get_mapping(self, uid: str) -> dict | None:
        uid_normalized = uid.upper()
        result = (
            await self.env.DB.prepare(
                "SELECT uid, filename, name, drm_config FROM mappings WHERE uid = ? LIMIT 1"
            )
            .bind(uid_normalized)
            .all()
        )
        rows = _js_to_py(result.results)
        if not rows:
            return None

        row = rows[0]
        drm_config = self._default_drm_config()
        drm_raw = _field(row, "drm_config")
        if drm_raw:
            try:
                parsed = json.loads(str(drm_raw))
                drm_config = self._normalize_drm_config(parsed)
            except Exception:
                drm_config = self._default_drm_config()

        filename = str(_field(row, "filename", DEFAULT_FILENAME))
        return {
            "uid": str(_field(row, "uid", uid_normalized)).upper(),
            "filename": filename,
            "name": _field(row, "name"),
            "drm": drm_config,
        }

    async def _list_mappings(self) -> list[dict]:
        result = await self.env.DB.prepare(
            "SELECT uid, filename, name, drm_config FROM mappings ORDER BY updated_at DESC"
        ).all()
        rows = _js_to_py(result.results) or []

        mappings: list[dict] = []
        for row in rows:
            drm_config = self._default_drm_config()
            drm_raw = _field(row, "drm_config")
            if drm_raw:
                try:
                    drm_config = self._normalize_drm_config(json.loads(str(drm_raw)))
                except Exception:
                    drm_config = self._default_drm_config()

            mappings.append(
                {
                    "uid": str(_field(row, "uid", "")).upper(),
                    "filename": str(_field(row, "filename", DEFAULT_FILENAME)),
                    "name": _field(row, "name"),
                    "drm": drm_config,
                }
            )
        return mappings

    async def _delete_mapping(self, uid: str) -> bool:
        uid_normalized = str(uid or "").strip().upper()
        if not uid_normalized:
            return False
        await self.env.DB.prepare("DELETE FROM mappings WHERE uid = ?").bind(uid_normalized).run()
        return True

    async def _list_assets(self, prefix: str = "", cursor: str | None = None, limit: int = 100):
        bucket = getattr(self.env, "VIDEO_BUCKET", None)
        if not bucket:
            raise ValueError("VIDEO_BUCKET binding is missing")

        options: dict[str, object] = {
            "limit": max(1, min(limit, 1000)),
        }
        if prefix:
            options["prefix"] = prefix
        if cursor:
            options["cursor"] = cursor

        result = await bucket.list(to_js(options))
        raw_items = _js_to_py(getattr(result, "objects", [])) or []
        items: list[dict] = []
        for obj in raw_items:
            key = str(_field(obj, "key", ""))
            size = _field(obj, "size")
            uploaded = _field(obj, "uploaded")
            items.append(
                {
                    "key": key,
                    "size": int(size) if size is not None else 0,
                    "uploaded": str(uploaded) if uploaded is not None else None,
                }
            )

        return {
            "items": items,
            "truncated": bool(getattr(result, "truncated", False)),
            "cursor": str(getattr(result, "cursor", "")) or None,
        }

    async def _upload_asset(
        self,
        request,
        key: str,
        content_type: str | None = None,
        cache_control: str | None = None,
    ):
        bucket = getattr(self.env, "VIDEO_BUCKET", None)
        if not bucket:
            raise ValueError("VIDEO_BUCKET binding is missing")

        raw_body = await self._read_binary_body(request)
        body = self._coerce_js_body(raw_body)
        body_len = self._estimate_body_size(raw_body)
        if body_len <= 0:
            body_len = self._estimate_body_size(body)
        if body_len <= 0:
            raise ValueError("empty upload body")

        put_options: dict[str, object] = {}
        http_metadata: dict[str, str] = {}
        if content_type:
            http_metadata["contentType"] = content_type
        if cache_control:
            http_metadata["cacheControl"] = cache_control
        if http_metadata:
            put_options["httpMetadata"] = http_metadata

        if put_options:
            await bucket.put(key, body, to_js(put_options))
        else:
            await bucket.put(key, body)

        return {"key": key, "size": body_len}

    async def _delete_asset(self, key: str):
        bucket = getattr(self.env, "VIDEO_BUCKET", None)
        if not bucket:
            raise ValueError("VIDEO_BUCKET binding is missing")
        await bucket.delete(key)
        return {"key": key}

    def _play_path(self, session_token: str, object_key: str) -> str:
        return f"/play/{quote(session_token, safe='')}/{quote(object_key, safe='/')}"

    def _license_path(self, session_token: str, drm_type: str) -> str:
        return f"/license/{quote(session_token, safe='')}/{quote(drm_type, safe='')}"

    def _certificate_path(self, session_token: str, drm_type: str) -> str:
        return f"/certificate/{quote(session_token, safe='')}/{quote(drm_type, safe='')}"

    def _derive_media_prefix(self, mapping: dict) -> str:
        drm = mapping.get("drm") or {}
        for candidate in (
            drm.get("hls_manifest"),
            drm.get("dash_manifest"),
            mapping.get("filename"),
        ):
            if not candidate:
                continue
            key = _normalize_media_key(candidate)
            parent = posixpath.dirname(key).strip("/")
            if parent:
                return f"{parent}/"
            return ""
        return ""

    def _issue_playback_session(self, uid: str, mapping: dict) -> str:
        drm = mapping.get("drm") or self._default_drm_config()
        merged_headers: dict[str, dict[str, str]] = {}
        configured_headers = drm.get("headers") or {}
        for drm_type in ("widevine", "fairplay", "playready"):
            headers = self._default_license_headers(drm_type)
            headers.update(_normalize_string_dict(configured_headers.get(drm_type)))
            if headers:
                merged_headers[drm_type] = headers

        payload = {
            "uid": uid,
            "prefix": self._derive_media_prefix(mapping),
            "hls": drm.get("hls_manifest"),
            "dash": drm.get("dash_manifest"),
            "lic": drm.get("licenses", {}),
            "cer": drm.get("certificates", {}),
            "hdr": merged_headers,
            "exp": int(time.time()) + self._playback_ttl_seconds(),
        }
        return self._issue_signed_payload(payload, self._playback_secret())

    def _validate_playback_session(self, token: str) -> dict | None:
        return self._validate_signed_payload(token, self._playback_secret())

    def _build_drm_playback_descriptor(self, origin: str, uid: str, mapping: dict) -> dict:
        session_token = self._issue_playback_session(uid, mapping)
        drm = mapping.get("drm") or self._default_drm_config()
        hls_manifest = drm.get("hls_manifest")
        dash_manifest = drm.get("dash_manifest")

        hls_url = f"{origin}{self._play_path(session_token, hls_manifest)}" if hls_manifest else None
        dash_url = (
            f"{origin}{self._play_path(session_token, dash_manifest)}" if dash_manifest else None
        )

        drm_systems: dict[str, dict] = {}
        license_urls: dict[str, str] = {}
        configured_license_urls = drm.get("licenses") or {}
        configured_certificate_urls = drm.get("certificates") or {}
        configured_headers = drm.get("headers") or {}

        for drm_type in ("widevine", "fairplay", "playready"):
            upstream_license = configured_license_urls.get(drm_type) or self._default_license_url(
                drm_type
            )
            upstream_certificate = configured_certificate_urls.get(
                drm_type
            ) or self._default_certificate_url(drm_type)
            header_map = self._default_license_headers(drm_type)
            header_map.update(_normalize_string_dict(configured_headers.get(drm_type)))

            system: dict[str, object] = {}
            if upstream_license:
                proxy_license_url = f"{origin}{self._license_path(session_token, drm_type)}"
                system["license_url"] = proxy_license_url
                license_urls[drm_type] = proxy_license_url
            if upstream_certificate:
                proxy_certificate_url = (
                    f"{origin}{self._certificate_path(session_token, drm_type)}"
                )
                system["certificate_url"] = proxy_certificate_url
            if header_map:
                system["headers"] = header_map

            if system:
                drm_systems[drm_type] = system

        default_url = hls_url or dash_url
        return {
            "type": "drm",
            "default_url": default_url,
            "hls_url": hls_url,
            "dash_url": dash_url,
            "licenses": license_urls,
            "drm": drm_systems,
            "session_token": session_token,
        }

    def _rewrite_manifest_uri(
        self,
        raw_uri: str,
        base_dir: str,
        session_token: str,
        playback_claims: dict,
    ) -> str:
        uri = str(raw_uri or "").strip()
        if not uri:
            return uri

        licenses = playback_claims.get("lic") if isinstance(playback_claims, dict) else {}
        if uri == HLS_FAIRPLAY_LICENSE_PLACEHOLDER and isinstance(licenses, dict):
            if licenses.get("fairplay"):
                return self._license_path(session_token, "fairplay")

        certificates = playback_claims.get("cer") if isinstance(playback_claims, dict) else {}
        if uri == HLS_FAIRPLAY_CERTIFICATE_PLACEHOLDER and isinstance(certificates, dict):
            if certificates.get("fairplay"):
                return self._certificate_path(session_token, "fairplay")

        parsed = urlparse(uri)
        if parsed.scheme in ("http", "https", "skd", "data"):
            return uri

        if not parsed.path:
            return uri

        target_key = _relative_key(base_dir, parsed.path)
        rewritten = self._play_path(session_token, target_key)
        if parsed.query:
            rewritten = f"{rewritten}?{parsed.query}"
        if parsed.fragment:
            rewritten = f"{rewritten}#{parsed.fragment}"
        return rewritten

    def _rewrite_hls_manifest(
        self,
        manifest_text: str,
        current_key: str,
        session_token: str,
        playback_claims: dict,
    ) -> str:
        base_dir = posixpath.dirname(current_key)
        lines = manifest_text.splitlines()
        rewritten_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                rewritten_lines.append(line)
                continue

            if stripped.startswith("#"):
                if 'URI="' in line:
                    line = HLS_URI_ATTR_PATTERN.sub(
                        lambda match: 'URI="{}"'.format(
                            self._rewrite_manifest_uri(
                                match.group(1),
                                base_dir,
                                session_token,
                                playback_claims,
                            )
                        ),
                        line,
                    )
                rewritten_lines.append(line)
                continue

            rewritten_lines.append(
                self._rewrite_manifest_uri(stripped, base_dir, session_token, playback_claims)
            )

        suffix = "\n" if manifest_text.endswith("\n") else ""
        return "\n".join(rewritten_lines) + suffix

    async def _serve_bucket_object(
        self,
        request,
        object_key: str,
        cache_seconds: int,
        manifest_session_token: str | None = None,
        playback_claims: dict | None = None,
    ):
        bucket = getattr(self.env, "VIDEO_BUCKET", None)
        if not bucket:
            return _json_response({"error": "VIDEO_BUCKET binding is missing"}, status=500)

        method = str(request.method).upper()
        is_hls_manifest = object_key.lower().endswith(".m3u8")
        if manifest_session_token and is_hls_manifest:
            r2_object = await bucket.get(object_key)
            if not r2_object:
                return _json_response({"error": "Video not found"}, status=404)

            manifest_text = await r2_object.text()
            rewritten = self._rewrite_hls_manifest(
                manifest_text,
                object_key,
                manifest_session_token,
                playback_claims or {},
            )
            headers = {
                "content-type": "application/vnd.apple.mpegurl",
                "cache-control": f"public, max-age=0, s-maxage={cache_seconds}",
                "accept-ranges": "bytes",
            }
            etag = getattr(r2_object, "httpEtag", None)
            if etag:
                headers["etag"] = str(etag)

            return JsResponse.new(
                "" if method == "HEAD" else rewritten,
                to_js({"status": 200, "headers": headers}),
            )

        range_header = request.headers.get("range")
        r2_object = None
        if range_header:
            try:
                r2_object = await bucket.get(
                    object_key,
                    to_js({"range": str(range_header)}),
                )
            except Exception:
                r2_object = await bucket.get(object_key)
        else:
            r2_object = await bucket.get(object_key)

        if not r2_object:
            return _json_response({"error": "Video not found"}, status=404)

        headers = {
            "cache-control": f"public, max-age=0, s-maxage={cache_seconds}",
            "accept-ranges": "bytes",
        }

        metadata = getattr(r2_object, "httpMetadata", None)
        content_type = getattr(metadata, "contentType", None) if metadata else None
        headers["content-type"] = str(content_type or "application/octet-stream")

        etag = getattr(r2_object, "httpEtag", None)
        if etag:
            headers["etag"] = str(etag)

        status = 200
        size = getattr(r2_object, "size", None)
        if size is not None:
            try:
                headers["content-length"] = str(int(size))
            except Exception:
                pass

        range_info = getattr(r2_object, "range", None)
        if range_header and range_info is not None:
            try:
                start = int(getattr(range_info, "offset"))
                length = int(getattr(range_info, "length"))
                total = int(size) if size is not None else start + length
                end = start + length - 1
                headers["content-range"] = f"bytes {start}-{end}/{total}"
                headers["content-length"] = str(length)
                status = 206
            except Exception:
                pass

        if method == "HEAD":
            return JsResponse.new("", to_js({"status": status, "headers": headers}))

        return JsResponse.new(
            r2_object.body,
            to_js({"status": status, "headers": headers}),
        )

    def _default_license_url(self, drm_type: str) -> str | None:
        env_map = {
            "widevine": "DRM_WIDEVINE_LICENSE_URL",
            "fairplay": "DRM_FAIRPLAY_LICENSE_URL",
            "playready": "DRM_PLAYREADY_LICENSE_URL",
        }
        env_key = env_map.get(drm_type)
        if not env_key:
            return None
        value = getattr(self.env, env_key, None)
        if not value:
            return None
        value = str(value).strip()
        if not _is_absolute_http_url(value):
            return None
        return value

    def _default_certificate_url(self, drm_type: str) -> str | None:
        env_map = {
            "widevine": "DRM_WIDEVINE_CERTIFICATE_URL",
            "fairplay": "DRM_FAIRPLAY_CERTIFICATE_URL",
            "playready": "DRM_PLAYREADY_CERTIFICATE_URL",
        }
        env_key = env_map.get(drm_type)
        if not env_key:
            return None
        value = getattr(self.env, env_key, None)
        if not value:
            return None
        value = str(value).strip()
        if not _is_absolute_http_url(value):
            return None
        return value

    def _default_license_headers(self, drm_type: str) -> dict[str, str]:
        env_map = {
            "widevine": "DRM_WIDEVINE_LICENSE_HEADERS_JSON",
            "fairplay": "DRM_FAIRPLAY_LICENSE_HEADERS_JSON",
            "playready": "DRM_PLAYREADY_LICENSE_HEADERS_JSON",
        }
        env_key = env_map.get(drm_type)
        if not env_key:
            return {}
        raw = getattr(self.env, env_key, None)
        if not raw:
            return {}
        try:
            parsed = json.loads(str(raw))
        except Exception:
            return {}
        return _normalize_string_dict(parsed)

    async def _handle_map(self, request):
        try:
            body = await self._read_text_body(request)
            payload = json.loads(body) if body else {}
        except Exception:
            return _json_response({"error": "Invalid JSON body"}, status=400)

        uid = str(payload.get("uid", "")).strip().upper()
        if not uid:
            return _json_response({"error": "uid is required"}, status=400)

        name = payload.get("name")
        if name is not None:
            name = str(name)

        drm_payload = payload.get("drm")
        if drm_payload is None:
            legacy_drm_payload = {}
            for key in (
                "hls_manifest",
                "dash_manifest",
                "widevine_license_url",
                "fairplay_license_url",
                "playready_license_url",
                "widevine_certificate_url",
                "fairplay_certificate_url",
                "playready_certificate_url",
                "licenses",
                "certificates",
                "headers",
                "license_headers",
                "enabled",
            ):
                if key in payload:
                    legacy_drm_payload[key] = payload.get(key)
            if legacy_drm_payload:
                drm_payload = legacy_drm_payload

        try:
            drm_config = self._normalize_drm_config(drm_payload)
        except Exception as err:
            return _json_response({"error": str(err)}, status=400)

        filename = str(payload.get("filename", "")).strip()
        if not filename:
            filename = (
                drm_config.get("hls_manifest")
                or drm_config.get("dash_manifest")
                or DEFAULT_FILENAME
            )

        try:
            filename = _normalize_media_key(filename)
        except Exception:
            return _json_response({"error": "Invalid filename/object key"}, status=400)

        try:
            mapping = await self._upsert_mapping(uid, filename, name, drm_config)
        except Exception as err:
            return _json_response({"error": f"Failed to save mapping: {err}"}, status=500)
        return _json_response(mapping)

    async def _handle_verify(self, request):
        parsed_url = urlparse(str(request.url))
        params = parse_qs(parsed_url.query)
        p = params.get("p", [None])[0]
        m = params.get("m", [None])[0]
        if not p or not m:
            return _json_response(
                {"success": False, "error": "Missing p or m parameters"},
                status=400,
            )

        sdm_key_hex = str(getattr(self.env, "SDM_KEY_HEX", DEFAULT_SDM_KEY_HEX)).strip()
        try:
            sdm_key = binascii.unhexlify(sdm_key_hex)
            if len(sdm_key) != 16:
                raise ValueError("SDM key must be 16 bytes (32 hex chars)")

            decrypted = await _decrypt_sun_payload(p, sdm_key)
            if len(decrypted) < 7:
                raise ValueError("Decrypted payload too short")
            uid_hex = binascii.hexlify(decrypted[0:7]).decode("utf-8").upper()

            # Keep m required for protocol compatibility.
            mapping = await self._get_mapping(uid_hex)
            if not mapping:
                mapping = await self._upsert_mapping(
                    uid_hex,
                    DEFAULT_FILENAME,
                    f"Secure Card {uid_hex[-4:]}",
                    self._default_drm_config(),
                )

            token = self._issue_token(uid_hex, mapping["filename"])
            origin = f"{parsed_url.scheme}://{parsed_url.netloc}"
            stream_url = f"{origin}/stream?token={quote(token, safe='')}"
            return _json_response(
                {
                    "success": True,
                    "video_url": stream_url,
                    "uid": uid_hex,
                    "playback_mode": "drm"
                    if (mapping.get("drm") or {}).get("enabled")
                    else "file",
                }
            )
        except Exception:
            return _json_response(
                {"success": False, "error": "Invalid Signature or Key"},
                status=400,
            )

    async def _handle_stream(self, request):
        parsed_url = urlparse(str(request.url))
        params = parse_qs(parsed_url.query)
        token = params.get("token", [None])[0]
        mode = str(params.get("mode", ["redirect"])[0]).lower()
        if not token:
            return _json_response({"error": "Missing token"}, status=400)

        token_payload = self._validate_token(token)
        if not token_payload:
            return _json_response({"error": "Invalid or expired token"}, status=403)

        uid = str(token_payload.get("uid", "")).strip().upper()
        filename_from_token = str(token_payload.get("filename", "")).strip()
        if not uid and not filename_from_token:
            return _json_response({"error": "Invalid token payload"}, status=403)

        mapping = await self._get_mapping(uid) if uid else None
        if not mapping:
            fallback_filename = filename_from_token or DEFAULT_FILENAME
            try:
                fallback_filename = _normalize_media_key(fallback_filename)
            except Exception:
                return _json_response({"error": "Invalid media key in token"}, status=403)
            mapping = {
                "uid": uid or "UNKNOWN",
                "filename": fallback_filename,
                "name": None,
                "drm": self._default_drm_config(),
            }

        origin = f"{parsed_url.scheme}://{parsed_url.netloc}"
        drm_config = mapping.get("drm") or self._default_drm_config()
        if drm_config.get("enabled"):
            descriptor = self._build_drm_playback_descriptor(origin, mapping["uid"], mapping)
            if mode == "json":
                return _json_response({"success": True, "uid": mapping["uid"], "playback": descriptor})

            default_url = descriptor.get("default_url")
            if not default_url:
                return _json_response(
                    {"error": "DRM is enabled but no manifest is configured"},
                    status=500,
                )
            return JsResponse.new(
                "",
                to_js(
                    {
                        "status": 302,
                        "headers": {
                            "location": default_url,
                            "cache-control": "no-store",
                        },
                    }
                ),
            )

        try:
            media_key = _normalize_media_key(mapping.get("filename") or DEFAULT_FILENAME)
            media_url = self._issue_cdn_url(origin, media_key)
        except Exception:
            return _json_response({"error": "Invalid media key in token"}, status=403)

        descriptor = {"type": "file", "default_url": media_url}
        if mode == "json":
            return _json_response({"success": True, "uid": mapping["uid"], "playback": descriptor})

        return JsResponse.new(
            "",
            to_js(
                {
                    "status": 302,
                    "headers": {
                        "location": media_url,
                        "cache-control": "no-store",
                    },
                }
            ),
        )

    async def _handle_cdn_media(self, request, object_path: str):
        try:
            object_key = _safe_object_key(object_path)
        except Exception:
            return _json_response({"error": "Invalid media path"}, status=400)

        parsed_url = urlparse(str(request.url))
        params = parse_qs(parsed_url.query)
        exp = params.get("exp", [None])[0]
        sig = params.get("sig", [None])[0]
        if not exp or not sig:
            return _json_response({"error": "Missing media signature"}, status=403)

        if not self._validate_cdn_url(object_key, str(exp), str(sig)):
            return _json_response({"error": "Invalid or expired media signature"}, status=403)

        return await self._serve_bucket_object(
            request,
            object_key,
            cache_seconds=MEDIA_CACHE_SECONDS,
        )

    async def _handle_play_media(self, request, session_token: str, object_path: str):
        claims = self._validate_playback_session(session_token)
        if not claims:
            return _json_response({"error": "Invalid or expired playback session"}, status=403)

        try:
            object_key = _safe_object_key(object_path)
        except Exception:
            return _json_response({"error": "Invalid media path"}, status=400)

        prefix = str(claims.get("prefix", "") or "")
        if prefix and not object_key.startswith(prefix):
            return _json_response({"error": "Forbidden media path"}, status=403)

        return await self._serve_bucket_object(
            request,
            object_key,
            cache_seconds=min(self._playback_ttl_seconds(), 600),
            manifest_session_token=session_token,
            playback_claims=claims,
        )

    async def _handle_license_proxy(self, request, session_token: str, drm_type: str):
        method = str(request.method).upper()
        if method == "OPTIONS":
            return JsResponse.new("", to_js({"status": 204, "headers": _cors_headers()}))
        if method not in ("POST", "GET", "HEAD"):
            return _text_response("Method Not Allowed", status=405)

        claims = self._validate_playback_session(session_token)
        if not claims:
            return _json_response({"error": "Invalid or expired playback session"}, status=403)

        drm_type = drm_type.strip().lower()
        license_map = claims.get("lic")
        if not isinstance(license_map, dict):
            license_map = {}
        upstream_url = license_map.get(drm_type) or self._default_license_url(drm_type)
        if not upstream_url:
            return _json_response({"error": f"No {drm_type} license URL configured"}, status=404)

        if not _is_absolute_http_url(str(upstream_url)):
            return _json_response({"error": "Invalid license URL"}, status=500)

        proxy_headers: dict[str, str] = {}
        raw_header_map = claims.get("hdr")
        if isinstance(raw_header_map, dict):
            proxy_headers.update(_normalize_string_dict(raw_header_map.get(drm_type)))

        # Optional auth header for providers that expect static auth.
        static_auth = getattr(self.env, "DRM_LICENSE_AUTHORIZATION", None)
        if static_auth:
            proxy_headers["authorization"] = str(static_auth)

        content_type = request.headers.get("content-type")
        if content_type and "content-type" not in {
            header_name.lower() for header_name in proxy_headers.keys()
        }:
            proxy_headers["content-type"] = str(content_type)

        fetch_options = {"method": method, "headers": proxy_headers}
        if method == "POST":
            fetch_options["body"] = self._coerce_js_body(await self._read_binary_body(request))

        upstream = await js_fetch(str(upstream_url), to_js(fetch_options))
        status = int(upstream.status)
        response_headers = _cors_headers()

        upstream_content_type = upstream.headers.get("content-type")
        if upstream_content_type:
            response_headers["content-type"] = str(upstream_content_type)

        if method == "HEAD":
            body = ""
        else:
            body = await self._read_binary_body(upstream)

        return JsResponse.new(
            body,
            to_js({"status": status, "headers": response_headers}),
        )

    async def _handle_certificate_proxy(self, request, session_token: str, drm_type: str):
        method = str(request.method).upper()
        if method == "OPTIONS":
            return JsResponse.new("", to_js({"status": 204, "headers": _cors_headers()}))
        if method not in ("GET", "HEAD"):
            return _text_response("Method Not Allowed", status=405)

        claims = self._validate_playback_session(session_token)
        if not claims:
            return _json_response({"error": "Invalid or expired playback session"}, status=403)

        drm_type = drm_type.strip().lower()
        certificate_map = claims.get("cer")
        if not isinstance(certificate_map, dict):
            certificate_map = {}
        upstream_url = certificate_map.get(drm_type) or self._default_certificate_url(drm_type)
        if not upstream_url:
            return _json_response({"error": f"No {drm_type} certificate URL configured"}, status=404)

        if not _is_absolute_http_url(str(upstream_url)):
            return _json_response({"error": "Invalid certificate URL"}, status=500)

        proxy_headers: dict[str, str] = {}
        raw_header_map = claims.get("hdr")
        if isinstance(raw_header_map, dict):
            proxy_headers.update(_normalize_string_dict(raw_header_map.get(drm_type)))

        static_auth = getattr(self.env, "DRM_LICENSE_AUTHORIZATION", None)
        if static_auth:
            proxy_headers["authorization"] = str(static_auth)

        upstream = await js_fetch(
            str(upstream_url),
            to_js({"method": method, "headers": proxy_headers}),
        )
        status = int(upstream.status)
        response_headers = _cors_headers()

        upstream_content_type = upstream.headers.get("content-type")
        if upstream_content_type:
            response_headers["content-type"] = str(upstream_content_type)

        if method == "HEAD":
            body = ""
        else:
            body = await self._read_binary_body(upstream)

        return JsResponse.new(
            body,
            to_js({"status": status, "headers": response_headers}),
        )

    async def _handle_admin_page(self, request):
        auth = self._authorize_admin(request)
        if auth is None:
            return self._html_response(
                "<h1>401 Unauthorized</h1><p>Please login via Cloudflare Access.</p>",
                status=401,
            )
        if auth.get("error") == "forbidden_email":
            return self._html_response(
                "<h1>403 Forbidden</h1><p>Your email is not allowed.</p>",
                status=403,
            )
        return self._html_response(ADMIN_UI_HTML, status=200)

    async def _handle_admin_api(self, request, admin_subpath: str):
        method = str(request.method).upper()
        if method == "OPTIONS":
            return JsResponse.new("", to_js({"status": 204, "headers": _cors_headers()}))

        auth = self._authorize_admin(request)
        if auth is None:
            return self._admin_unauthorized_response()
        if auth.get("error") == "forbidden_email":
            return self._admin_forbidden_response()

        subpath = admin_subpath or "/"
        if not subpath.startswith("/"):
            subpath = f"/{subpath}"

        if subpath == "/me":
            if method != "GET":
                return _text_response("Method Not Allowed", status=405)
            return _json_response(
                {
                    "ok": True,
                    "auth": auth.get("auth"),
                    "email": auth.get("email"),
                }
            )

        if subpath == "/mappings":
            try:
                await self._ensure_schema()
            except Exception as err:
                return _json_response({"error": f"Schema initialization failed: {err}"}, status=500)
            if method == "GET":
                try:
                    items = await self._list_mappings()
                    return _json_response({"items": items})
                except Exception as err:
                    return _json_response({"error": f"Failed to list mappings: {err}"}, status=500)
            if method == "POST":
                return await self._handle_map(request)
            return _text_response("Method Not Allowed", status=405)

        if subpath.startswith("/mappings/"):
            try:
                await self._ensure_schema()
            except Exception as err:
                return _json_response({"error": f"Schema initialization failed: {err}"}, status=500)
            uid = unquote(subpath[len("/mappings/") :]).strip().upper()
            if not uid:
                return _json_response({"error": "uid is required"}, status=400)
            if method == "GET":
                try:
                    item = await self._get_mapping(uid)
                except Exception as err:
                    return _json_response({"error": f"Failed to load mapping: {err}"}, status=500)
                if not item:
                    return _json_response({"error": "mapping not found"}, status=404)
                return _json_response({"item": item})
            if method == "DELETE":
                try:
                    await self._delete_mapping(uid)
                except Exception as err:
                    return _json_response({"error": f"Failed to delete mapping: {err}"}, status=500)
                return _json_response({"success": True, "uid": uid})
            return _text_response("Method Not Allowed", status=405)

        if subpath == "/assets":
            if method != "GET":
                return _text_response("Method Not Allowed", status=405)
            parsed_url = urlparse(str(request.url))
            params = parse_qs(parsed_url.query)
            prefix = str(params.get("prefix", [""])[0] or "").strip()
            cursor = str(params.get("cursor", [""])[0] or "").strip() or None
            limit = _clamp_int(params.get("limit", ["100"])[0], 1, 1000, 100)
            try:
                result = await self._list_assets(prefix=prefix, cursor=cursor, limit=limit)
                return _json_response(result)
            except Exception as err:
                return _json_response({"error": str(err)}, status=500)

        if subpath == "/assets/upload":
            if method != "POST":
                return _text_response("Method Not Allowed", status=405)
            parsed_url = urlparse(str(request.url))
            params = parse_qs(parsed_url.query)
            key_raw = str(params.get("key", [""])[0] or "").strip()
            if not key_raw:
                return _json_response({"error": "key query parameter is required"}, status=400)
            try:
                key = _safe_object_key(key_raw)
            except Exception:
                return _json_response({"error": "invalid key"}, status=400)

            content_type = (
                request.headers.get("x-upload-content-type")
                or request.headers.get("content-type")
                or None
            )
            cache_control = request.headers.get("x-upload-cache-control") or None
            try:
                result = await self._upload_asset(
                    request,
                    key=key,
                    content_type=str(content_type).strip() if content_type else None,
                    cache_control=str(cache_control).strip() if cache_control else None,
                )
                return _json_response({"success": True, **result})
            except Exception as err:
                return _json_response({"error": str(err)}, status=500)

        if subpath == "/assets/sign":
            if method != "GET":
                return _text_response("Method Not Allowed", status=405)
            parsed_url = urlparse(str(request.url))
            params = parse_qs(parsed_url.query)
            key_raw = str(params.get("key", [""])[0] or "").strip()
            if not key_raw:
                return _json_response({"error": "key query parameter is required"}, status=400)
            try:
                key = _safe_object_key(key_raw)
                url = self._issue_cdn_url(f"{parsed_url.scheme}://{parsed_url.netloc}", key)
                return _json_response({"success": True, "key": key, "url": url})
            except Exception as err:
                return _json_response({"error": str(err)}, status=400)

        if subpath.startswith("/assets/"):
            key_raw = unquote(subpath[len("/assets/") :]).strip()
            if not key_raw:
                return _json_response({"error": "key is required"}, status=400)
            if method == "DELETE":
                try:
                    key = _safe_object_key(key_raw)
                    result = await self._delete_asset(key)
                    return _json_response({"success": True, **result})
                except Exception as err:
                    return _json_response({"error": str(err)}, status=500)
            return _text_response("Method Not Allowed", status=405)

        return _text_response("Not Found", status=404)

    async def fetch(self, request):
        method = str(request.method).upper()
        parsed_url = urlparse(str(request.url))
        path = parsed_url.path or "/"

        if path == "/health":
            return _json_response({"ok": True, "runtime": "cloudflare-worker-python"})

        if path in ("/admin", "/admin/"):
            if method != "GET":
                return _text_response("Method Not Allowed", status=405)
            return await self._handle_admin_page(request)

        if path == "/admin/api" or path.startswith("/admin/api/"):
            subpath = path[len("/admin/api") :]
            return await self._handle_admin_api(request, subpath)

        if path == "/map":
            if method != "POST":
                return _text_response("Method Not Allowed", status=405)
            await self._ensure_schema()
            return await self._handle_map(request)

        if path == "/verify":
            if method != "GET":
                return _text_response("Method Not Allowed", status=405)
            await self._ensure_schema()
            return await self._handle_verify(request)

        if path == "/stream":
            if method != "GET":
                return _text_response("Method Not Allowed", status=405)
            await self._ensure_schema()
            return await self._handle_stream(request)

        if path.startswith("/cdn/"):
            if method not in ("GET", "HEAD"):
                return _text_response("Method Not Allowed", status=405)
            object_path = path[len("/cdn/") :]
            return await self._handle_cdn_media(request, object_path)

        if path.startswith("/play/"):
            if method not in ("GET", "HEAD"):
                return _text_response("Method Not Allowed", status=405)
            rest = path[len("/play/") :]
            parts = rest.split("/", 1)
            if len(parts) != 2:
                return _json_response({"error": "Invalid play path"}, status=400)
            session_token = unquote(parts[0])
            object_path = parts[1]
            return await self._handle_play_media(request, session_token, object_path)

        if path.startswith("/license/"):
            rest = path[len("/license/") :]
            parts = rest.split("/", 1)
            if len(parts) != 2:
                return _json_response({"error": "Invalid license path"}, status=400)
            session_token = unquote(parts[0])
            drm_type = unquote(parts[1])
            return await self._handle_license_proxy(request, session_token, drm_type)

        if path.startswith("/certificate/"):
            rest = path[len("/certificate/") :]
            parts = rest.split("/", 1)
            if len(parts) != 2:
                return _json_response({"error": "Invalid certificate path"}, status=400)
            session_token = unquote(parts[0])
            drm_type = unquote(parts[1])
            return await self._handle_certificate_proxy(request, session_token, drm_type)

        if path == "/mappings":
            if method != "GET":
                return _text_response("Method Not Allowed", status=405)
            await self._ensure_schema()
            mappings = await self._list_mappings()
            return _json_response(mappings)

        return _text_response("Not Found", status=404)
