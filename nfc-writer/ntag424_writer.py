#!/usr/bin/env python3
"""
NTAG 424 DNA Writer - 兼容 MagTek IC-02 (libOURMIFARE.so)

使用 icmcu.com 的 libOURMIFARE 库操作 NTAG 424 DNA 卡片
功能:
  1. 读取卡片 UID
  2. 认证密钥
  3. 写入 NDEF URL (带 SUN/SDM 配置)
  4. 更改密钥
"""

import ctypes
import sys
import os
import struct  # 添加 struct 导入

# 库文件路径 (可配置)
LIB_PATH = os.environ.get(
    'OURMIFARE_LIB',
    os.path.join(os.path.dirname(__file__), 'libOURMIFARE.so')
)

# 默认密钥 (出厂默认全0)
DEFAULT_KEY = bytes([0x00] * 16)


class Ntag424Error(Exception):
    """NTAG 424 操作错误"""
    pass


class Ntag424Writer:
    """NTAG 424 DNA 写卡器 (使用 libOURMIFARE)"""
    
    # 错误码映射
    ERROR_CODES = {
        0: "成功",
        3: "CPU卡还未激活",
        8: "未寻到卡",
        23: "发卡器未连接或库文件错误",
        52: "操作成功(有附加信息)",
        53: "无线通信失败，请重新放卡",
        55: "还有剩余数据未接收",
    }
    
    # 卡片返回码映射
    CARD_STATUS = {
        "9000": "成功",
        "9100": "成功",
        "91AE": "认证失败，密钥错误",
        "919D": "未验证密码，该指令无法操作",
        "91A0": "请求的 AID 不存在",
        "6A82": "文件未找到",
        "6982": "不满足安全状态",
    }
    
    def __init__(self, lib_path: str = None):
        """初始化"""
        self.lib_path = lib_path or LIB_PATH
        self.lib = None
        self.connected = False
        self._load_library()
    
    def _load_library(self):
        """加载动态库"""
        if not os.path.exists(self.lib_path):
            raise Ntag424Error(f"库文件不存在: {self.lib_path}")
        
        try:
            self.lib = ctypes.cdll.LoadLibrary(self.lib_path)
            print(f"✓ 库加载成功: {self.lib_path}")
        except Exception as e:
            raise Ntag424Error(f"加载库失败: {e}")
    
    def _check_status(self, status: int, operation: str = "操作"):
        """检查返回状态码"""
        status = status % 256
        if status == 0 or status == 52:
            return True
        
        error_msg = self.ERROR_CODES.get(status, f"未知错误 ({status})")
        raise Ntag424Error(f"{operation}失败: {error_msg}")
    
    def _parse_card_status(self, status_bytes: bytes) -> tuple:
        """解析卡片返回状态"""
        status_hex = f"{status_bytes[0]:02X}{status_bytes[1]:02X}"
        msg = self.CARD_STATUS.get(status_hex, f"未知状态 ({status_hex})")
        success = status_hex in ("9000", "9100")
        return success, status_hex, msg
    
    # ==================== 基础操作 ====================
    
    def beep(self, duration_ms: int = 50):
        """发出蜂鸣声"""
        status = self.lib.pcdbeep(duration_ms) % 256
        return status == 0
    
    def get_device_serial(self) -> str:
        """获取读卡器序列号"""
        devno = bytes(4)
        status = self.lib.pcdgetdevicenumber(devno) % 256
        self._check_status(status, "获取设备序列号")
        
        serial = '-'.join(f'{b:02X}' for b in devno)
        self.connected = True
        return serial
    
    def request_card(self) -> dict:
        """
        寻卡并激活
        
        Returns:
            dict: 包含 uid, params, version, manufacturer 等信息
        """
        mypiccserial = bytes(7)
        myparam = bytes(4)
        AtqaSak = bytes(3)
        myver = bytes(1)
        mycode = bytes(1)
        
        status = self.lib.cpurequest1(mypiccserial, myparam, myver, mycode, AtqaSak) % 256
        self._check_status(status, "寻卡")
        
        # 判断 UID 长度
        if AtqaSak[0] // 64 > 0:
            # 7 字节 UID (NTAG 424 DNA)
            uid = ''.join(f'{b:02X}' for b in mypiccserial[:7])
            card_type = "NTAG424DNA"
        else:
            # 4 字节 UID
            uid = ''.join(f'{b:02X}' for b in mypiccserial[:4])
            card_type = "FM1208CPU"
        
        self.beep(30)
        
        return {
            'uid': uid,
            'card_type': card_type,
            'params': ''.join(f'{b:02X}' for b in myparam),
            'version': f'{myver[0]:02X}',
            'manufacturer': f'{mycode[0]:02X}',
        }
    
    # ==================== 应用选择 ====================
    
    def select_application(self, aid: str = "D2760000850101"):
        """
        选择卡内应用
        
        Args:
            aid: 应用 ID (默认为 NTAG 424 DNA NDEF 应用)
                 - D2760000850100: NTAG 424 DNA 主应用
                 - D2760000850101: NTAG 424 DNA NDEF 应用
        """
        aid_bytes = bytes.fromhex(aid.replace(' ', ''))
        aid_len = len(aid_bytes)
        
        # 构建 ISO SELECT 命令
        cmd = bytes.fromhex(f"00A40400{aid_len:02X}") + aid_bytes
        
        revbuf = bytes(128)
        revbuflen = bytes(4)
        
        status = self.lib.cpuisoapdu(cmd, len(cmd), revbuf, revbuflen) % 256
        self._check_status(status, "选择应用")
        
        # 解析返回
        ret_hex = ''.join(f'{revbuf[i]:02X}' for i in range(revbuflen[0]))
        print(f"✓ 应用已选择，返回: {ret_hex}")
        return ret_hex
    
    # ==================== 密钥操作 ====================
    
    def authenticate(self, key: bytes = None, key_id: int = 0, key_type: int = 0) -> bool:
        """
        认证密钥 (EV2 认证)
        
        Args:
            key: 16 字节 AES 密钥 (默认全 0)
            key_id: 密钥 ID (0-4)
            key_type: 密钥类型 (0=AES)
        
        Returns:
            bool: 是否成功
        """
        if key is None:
            key = DEFAULT_KEY
        
        if len(key) != 16:
            raise Ntag424Error("密钥必须是 16 字节")
        
        retsw = bytes(2)
        status = self.lib.desfireauthkeyev2(key, key_id, key_type, retsw) % 256
        
        success, status_hex, msg = self._parse_card_status(retsw)
        
        if status == 0 and success:
            self.beep(30)
            print(f"✓ 密钥 {key_id} 认证成功")
            return True
        else:
            print(f"✗ 认证失败: {msg} ({status_hex})")
            return False
    
    def change_key(self, new_key: bytes, key_id: int = 0, old_key: bytes = None) -> bool:
        """
        更改密钥
        
        Args:
            new_key: 新的 16 字节密钥
            key_id: 要更改的密钥 ID
            old_key: 当前密钥 (用于认证)
        
        Returns:
            bool: 是否成功
        """
        if old_key is None:
            old_key = DEFAULT_KEY
        
        if len(new_key) != 16 or len(old_key) != 16:
            raise Ntag424Error("密钥必须是 16 字节")
        
        retsw = bytes(2)
        status = self.lib.ntagchangkey(new_key, key_id, 1, old_key, retsw) % 256
        
        success, status_hex, msg = self._parse_card_status(retsw)
        
        if status == 0 and success:
            self.beep(30)
            print(f"✓ 密钥 {key_id} 更改成功")
            return True
        else:
            print(f"✗ 更改密钥失败: {msg} ({status_hex})")
            return False
    
    # ==================== NDEF 操作 ====================
    
    def write_ndef_url(
        self,
        url: str,
        title: str = "",
        auth_key: bytes = None,
        auth_key_id: int = 0,
        require_auth: bool = False,
        uri_header: int = 1
    ) -> bool:
        """
        写入 NDEF URL 记录
        
        Args:
            url: URL 地址 (不含协议头，如 "example.com/path")
            title: 标题 (可选)
            auth_key: 认证密钥 (如需认证)
            auth_key_id: 认证密钥 ID
            require_auth: 是否需要认证
            uri_header: URI 前缀代码 (默认 1 = https://www.)
        """
        # 控制字和认证密钥
        ctrl_word = 0x00
        picc_key_str = "00" * 18  # 不需要认证
        
        if require_auth:
            if auth_key is None:
                auth_key = DEFAULT_KEY
            ctrl_word = 0x40
            picc_key_str = f"04{auth_key_id:02X}" + auth_key.hex()
        
        picc_key_buf = bytes.fromhex(picc_key_str)
        
        # 语言代码
        lang_code = b"en"
        title_bytes = title.encode('utf-8') if title else b""
        url_bytes = url.encode('utf-8')
        
        # URI 前缀
        uri_header_index = uri_header
        
        # 清空写卡缓冲区
        self.lib.tagbuf_forumtype4_clear()
        
        # 添加 URI 到缓冲区
        status = self.lib.tagbuf_adduri(
            lang_code, len(lang_code),
            title_bytes, len(title_bytes),
            uri_header_index,
            url_bytes, len(url_bytes)
        ) % 256
        
        if status != 0:
            raise Ntag424Error(f"添加 URI 到缓冲区失败: {status}")
        
        # 写入标签
        mypiccserial = bytes(7)
        mypiccseriallen = bytes(1)
        
        status = self.lib.forumtype4_write_ndeftag(
            ctrl_word,
            mypiccserial,
            mypiccseriallen,
            picc_key_buf
        ) % 256
        
        self._check_status(status, "写入 NDEF")
        
        uid = ''.join(f'{mypiccserial[i]:02X}' for i in range(mypiccseriallen[0]))
        self.beep(30)
        print(f"✓ NDEF URL 写入成功，UID: {uid}")
        return True
    
    def read_ndef(self, auth_key: bytes = None, auth_key_id: int = 0, require_auth: bool = False) -> str:
        """
        读取 NDEF 记录
        
        Returns:
            str: NDEF 内容
        """
        ctrl_word = 0x00
        picc_key_str = "00" * 18
        
        if require_auth:
            if auth_key is None:
                auth_key = DEFAULT_KEY
            ctrl_word = 0x40
            picc_key_str = f"04{auth_key_id:02X}" + auth_key.hex()
        
        picc_key_buf = bytes.fromhex(picc_key_str)
        
        mypiccserial = bytes(7)
        mypiccseriallen = bytes(1)
        ndefbuf = bytes(512)
        ndeflen = bytes(4)
        
        status = self.lib.forumtype4_read_ndeftag(
            ctrl_word,
            mypiccserial,
            mypiccseriallen,
            picc_key_buf,
            ndefbuf,
            ndeflen
        ) % 256
        
        self._check_status(status, "读取 NDEF")
        
        # 解析长度
        length = ndeflen[0] | (ndeflen[1] << 8)
        ndef_data = bytes(ndefbuf[:length])
        
        self.beep(30)
        print(f"✓ NDEF 读取成功，长度: {length} 字节")
        return ndef_data.hex()
    
    # ==================== SUN/SDM 配置 ====================
    
    # ==================== SUN/SDM 配置 ====================
    
    def configure_sun(
        self,
        picc_offset: int,
        mac_offset: int,
        sdm_mac_input_offset: int = 0,
        sdm_enc_length: int = 0,
        use_enc_file_data: bool = True
    ) -> bool:
        """
        配置 SUN/SDM (使用 libOURMIFARE)
        参考 CallNtag424mainwindow.py 的 pb_ChangeConfig_clicked 实现
        
        Args:
            picc_offset: 对应 SDMEncOffset (p= value start)
            mac_offset: 对应 SDMMACOffset (m= value start)
            sdm_mac_input_offset: MAC 计算起始位置 (通常为 0)
            sdm_enc_length: 加密数据长度 (通常 32 bytes for UID+Ctr+Pad)
            use_enc_file_data: 是否使用 EncFileData 模式
        """
        if sdm_enc_length == 0 and use_enc_file_data:
            sdm_enc_length = 32  # 默认 32 字节

        configdata = bytearray(32)
        j = 0 # 索引

        # [0] FileOption
        # Bit 6: SDM Enabled (0x40)
        # Bit 0-1: CommMode (0=Plain) -> 0x40 (Plain + SDM)
        configdata[0] = 0x40 

        # [1] AccessRights (Change | RW)
        # Change: Key 0 (0x0), RW: Key 0 (0x0 -> 0x00)
        # CallNtag logic: i = KeyID. If KeyID < 5 (0-4), val = KeyID.
        # Shift RW by 4 bits.
        # We use Key 0 for everything.
        # Change=0, RW=0 => 0x00.
        configdata[1] = 0x00

        # [2] AccessRights (Write | Read)
        # Write: Key 0 (0x0), Read: Free (0xE)
        # Write (low nibble? No, Check code)
        # Code: i = settingsbuf[3] % 16 (WriteOnly). i = settingsbuf[3] // 16 (ReadOnly).
        # Wait, settingsbuf is response.
        # configdata[2] construction:
        # Write (bits 0-3): Key 0 -> 0x0.
        # Read (bits 4-7): Free (0xE) -> 0xE0.
        # So configdata[2] = 0xE0.
        configdata[2] = 0xE0

        j = 3

        # [3] SDMOptions
        # Bit 0: ASCII (0x01) -> We use ASCII
        configdata[3] = 0x01 
        
        # Enable SDM features
        if use_enc_file_data:
            configdata[3] |= 0x10  # SDMENCFileData
            # Usually implies UID Mirror or ReadCtr Mirror?
            # Code: if (configdata[3] & 0x40 > 0) checks.
            # We want standard SUN: Encrypted PICC Data.
            # Actually, standard SUN is often just "EncFile" bit if we want 'p' param.
            # Let's try JUST 0x10 | 0x01.
            pass
        else:
            # Plain Mirroring: UID(0x80) | ReadCtr(0x40)
            configdata[3] |= 0xC0

        # [4] SDMAccessRights (CtrRet | MetaRead? No)
        # Byte 4: 
        #   High Nibble: ?
        #   Low Nibble: SDMCtrRet Access (Key 1 or Free?)
        #   Code: configdata[4] = 0xF0 + KeyID.
        #   We use Key 1 for reading Counter? Or Key 0? Or Free?
        #   Usually MetaRead/CtrRet requires auth?
        #   Let's set to Key 0 (0) or Key 1 (1).
        #   Let's use Key 0 for now.
        #   High Nibble seems fixed to F? (0xF0)
        configdata[4] = 0xF0 # CtrRet=0 (Key 0)

        # [5] SDMAccessRights (MetaRead | FileRead)
        #   High Nibble: MetaRead Access
        #   Low Nibble: FileRead Access (MAC Key)
        #   We use Key 0 for MetaRead? Or Free (0xE)?
        #   If Free, we can read params without auth. 0xE0.
        #   MAC Key: Key 0 (0x0).
        #   So 0xE0.
        configdata[5] = 0xE0 

        j = 6

        # Offsets
        # Logic from CallNtag:
        # if (configdata[5] & 0xF0) < 0x50: (MetaRead requires Key 0-4) -> Offset at 6,7,8.
        # if MetaRead == 0xE0 (Free):
        #    if UIDMirror (0x80): Offset at 6,7,8. j=9.
        #    if CountMirror (0x40): Offset at j, j+1, j+2.
        
        # We set MetaRead=0xE0 (Free).
        # If we use EncFile (0x10), we didn't set 0x80 or 0x40.
        # So we skip UID/Ctr offsets here.
        
        # Next block:
        # if (configdata[5] & 0x0F) != 0x0F: (FileRead/MAC Key is set, 0x0 in our case)
        #    Append SDMMACInputOffset (3 bytes).
        #    if SDMENCFileData (0x10) set:
        #       Append SDMENCOffset (3 bytes)
        #       Append SDMENCLength (3 bytes)
        #    Append SDMMACOffset (3 bytes)
        
        if (configdata[5] & 0x0F) != 0x0F:
            # 1. SDMMACInputOffset
            offset_bytes = struct.pack("<I", sdm_mac_input_offset)[:3]
            configdata[j] = offset_bytes[0]; configdata[j+1] = offset_bytes[1]; configdata[j+2] = offset_bytes[2]
            j += 3
            
            if (configdata[3] & 0x10) > 0: # EncFileData
                # 2. SDMENCOffset (p= start)
                offset_bytes = struct.pack("<I", picc_offset)[:3]
                configdata[j] = offset_bytes[0]; configdata[j+1] = offset_bytes[1]; configdata[j+2] = offset_bytes[2]
                j += 3
                
                # 3. SDMENCLength (Length of data to encrypt)
                offset_bytes = struct.pack("<I", sdm_enc_length)[:3]
                configdata[j] = offset_bytes[0]; configdata[j+1] = offset_bytes[1]; configdata[j+2] = offset_bytes[2]
                j += 3
                
            # 4. SDMMACOffset (m= start)
            offset_bytes = struct.pack("<I", mac_offset)[:3]
            configdata[j] = offset_bytes[0]; configdata[j+1] = offset_bytes[1]; configdata[j+2] = offset_bytes[2]
            j += 3

        # Call Library Function
        # ntagchangefilesettings(comm_mode, fileno, data, len, sw)
        # comm_mode: 0=Plain, 1=MAC, 3=Full (Code says 3 for Full? Enum?)
        # Code: if index==2: configdata[0]=3 (Wait, that was configdata construction).
        # Call: Objdll.ntagchangefilesettings(currentIndex, ...)
        # currentIndex 0=Plain, 1=MAC, 2=Full.
        # But changefilesettings usually requires Auth.
        # If we Authenticated with Key 0 (Master), and Master key settings require Auth for Change,
        # we typically use CommMode.Full (3? or 2?) or MAC.
        # The Python code uses `self.comboBox_RWConfigConnModly.currentIndex()`.
        # Items: "明文", "密文+MAC保护".
        # So 0 or 1.
        # If 1 -> "密文+MAC".
        # Let's try 1 (MAC/Full). Since we have the library, it handles it.
        
        print(f"Configuring SDM (Len={j})...")
        databuf = bytes(configdata[:j])
        retsw = bytes(2)
        
        # 1 = Encrypted+MAC? (Based on UI "密文+MAC保护")
        # Try 0 (Plain) if 1 fails with 91AE
        res = self.lib.ntagchangefilesettings(0, 2, databuf, j, retsw) % 256
        
        success, status_hex, msg = self._parse_card_status(retsw)
        if res == 0 and success:
            self.beep(20)
            print("✓ SDM 配置成功")
            return True
        else:
            print(f"✗ SDM 配置失败: {msg} ({status_hex})")
            return False

def main():
    """演示用法"""
    print("=" * 50)

    print("NTAG 424 DNA Writer (libOURMIFARE)")
    print("=" * 50)
    
    try:
        writer = Ntag424Writer()
        
        # 获取设备信息
        serial = writer.get_device_serial()
        print(f"✓ 读卡器序列号: {serial}")
        
        # 寻卡
        print("\n请将卡片放在读卡器上...")
        card_info = writer.request_card()
        print(f"✓ 卡片类型: {card_info['card_type']}")
        print(f"✓ 卡片 UID: {card_info['uid']}")
        print(f"✓ 厂商代码: {card_info['manufacturer']}")
        
        # 选择应用
        writer.select_application("D2760000850101")
        
        # 默认密钥认证
        print("\n尝试使用默认密钥认证...")
        if writer.authenticate(DEFAULT_KEY, 0):
            print("✓ 默认密钥认证成功")
        else:
            print("✗ 默认密钥认证失败，卡片可能已配置其他密钥")
        
        print("\n" + "=" * 50)
        print("基础功能测试完成！")
        print("=" * 50)
        
    except Ntag424Error as e:
        print(f"\n❌ 错误: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ 未知错误: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
