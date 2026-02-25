# NFC 424 DNA 写卡工具

这个目录包含了用于配置 NTAG 424 DNA 卡片的工具脚本。

## ⚠️ 重要说明

NTAG 424 DNA 的 SUN (Secure Unique NFC) 功能配置涉及复杂的 AES-128 加密认证（EV2 Secure Messaging）。

从零实现完整的 Python 协议栈比较耗时且容易出错。

**对于初期开发 (20种卡，每种几十张)，强烈建议使用以下方案：**

### 方案 A：使用 NXP 官方 APP (最快，无需写代码)

1. 下载 **NXP TagWriter** (Android/iOS)。
2. 选择 "Write" -> "New Dataset" -> "Link"。
3. 输入 URL: `https://你的域名/verify?d=00000000000000000000000000000000` (保留32个0作为占位)。
4. 点击 "Configure MArgin/Mirroring" (关键步骤)。
   - Enable Mirroring: YES
   - Mirror UID: YES
   - Mirror Counter: YES
   - Enable SDM: YES
   - SDM Meta Read Access Right: key 0 (或 Free)
5. 点击 "Write" 并靠近卡片。

### 方案 B：使用 Python 脚本 (本工具)

如果你必须用电脑批量写卡：

1. **硬件**: 需要 ACR122U 或 PN532 读写器。
2. **环境**:
   ```bash
   pip install -r requirements.txt
   ```
3. **驱动**:
   - Linux: 需要安装 `pcscd` 和 `libacsccid1`
     ```bash
     sudo apt-get install pcscd libacsccid1
     sudo systemctl start pcscd
     ```
   - Mac: 通常自带，或安装驱动。

## 脚本说明

- `write_tag_demo.py`: 一个基础的连接和认证演示。由于完整的 EV2 协议非常长，这里仅展示了如何连接和通过默认密钥认证。

## 后端配合

无论用哪种方式写卡，你需要：
1. **记录密钥**: 写卡时设置的 AES Key (默认是全0，建议修改)。
2. **录入数据库**: 将这个 Key 和对应的 URL 录入到我们的后端数据库中。
