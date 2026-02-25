import time
import struct
import binascii
import hmac
import hashlib
from smartcard.System import readers
from smartcard.util import toHexString, toBytes
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Hash import CMAC

# --- 常量定义 ---

# NTAG 424 DNA 命令代码
CMD_ISO_SELECT = [0x00, 0xA4, 0x04, 0x00]
CMD_AUTH_EV2_FIRST = 0x71
CMD_CHANGE_KEY = 0xC4
CMD_GET_FILE_SETTINGS = 0xF5
CMD_CHANGE_FILE_SETTINGS = 0x5F
CMD_READ_DATA = 0xAD
CMD_WRITE_DATA = 0x8D

# 响应码
SW_SUCCESS = 0x9000

# 默认密钥 (出厂默认全0)
DEFAULT_KEY = bytes([0x00] * 16)

class Ntag424Error(Exception):
    pass

class Ntag424Writer:
    def __init__(self):
        self.connection = None
        self.session_key_enc = None
        self.session_key_mac = None
        self.ti = None  # Transaction Identifier
        self.cmd_counter = 0

    def connect(self):
        """连接到第一个可用的读卡器"""
        r = readers()
        if len(r) == 0:
            raise Ntag424Error("未找到读卡器")
        
        reader = r[0]
        print(f"使用读卡器: {reader}")
        self.connection = reader.createConnection()
        self.connection.connect()
        print("卡片已连接")

    def send_apdu(self, apdu):
        """发送原始APDU指令"""
        resp, sw1, sw2 = self.connection.transmit(apdu)
        status = (sw1 << 8) | sw2
        return resp, status

    def select_application(self):
        """选择 NTAG 424 DNA 应用"""
        # ISO Select AID
        aid = [0xD2, 0x76, 0x00, 0x00, 0x85, 0x01, 0x01]
        apdu = CMD_ISO_SELECT + [len(aid)] + aid
        resp, sw = self.send_apdu(apdu)
        if sw != SW_SUCCESS:
            raise Ntag424Error(f"选择应用失败: {hex(sw)}")
        print("应用已选择")

    def authenticate_ev2_first(self, key_no, key):
        """
        EV2 First Authentication
        这是最复杂的步骤，涉及AES双向认证和会话密钥生成
        """
        print(f"正在尝试使用密钥 {key_no} 认证...")
        
        # 1. 发送 AuthEv2First 命令 (Part 1)
        # Cmd(1) + KeyNo(1) + LenCap(2) + PCD_Cap(0-6)
        # 这里简化，不带 PCD_Cap
        apdu = [0x90, CMD_AUTH_EV2_FIRST, 0x00, 0x00, 0x02, key_no, 0x00, 0x00]
        resp, sw = self.send_apdu(apdu)
        
        if sw != 0x91AF: # 0x91AF 表示期待更多数据 (正常流程)
             raise Ntag424Error(f"认证第一步失败: {hex(sw)}")

        # 解析响应: RndB_enc(16)
        rnd_b_enc = bytes(resp)
        
        # 2. 本地生成 RndA
        rnd_a = get_random_bytes(16)
        
        # 3. 解密 RndB
        # IV 为全0 (对于 First Auth)
        iv = bytes(16)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        rnd_b = cipher.decrypt(rnd_b_enc)
        
        # 4. 生成 RndB' (左移1位)
        rnd_b_prime = rnd_b[1:] + rnd_b[:1]
        
        # 5. 加密 (RndA + RndB')
        token = rnd_a + rnd_b_prime
        iv = bytes(16) # 重新初始化IV
        cipher = AES.new(key, AES.MODE_CBC, iv)
        token_enc = cipher.encrypt(token)
        
        # 6. 发送 AuthEv2First 命令 (Part 2)
        # Cmd(1) + EncData(32)
        apdu = [0x90, 0xAF, 0x00, 0x00, 0x20] + list(token_enc) + [0x00]
        resp, sw = self.send_apdu(apdu)
        
        if sw != SW_SUCCESS:
             raise Ntag424Error(f"认证第二步失败: {hex(sw)}")

        # 7. 验证卡片返回的 RndA'
        # 响应包含: Enc(RndA') + MAC
        # 这里为了简化代码，暂不验证卡片返回的MAC (生产环境应该验证)
        # 重要的是我们成功进入了认证状态
        
        # 8. 生成会话密钥 (Session Keys)
        # 同样简化，用于后续加密通信。如果只是写NDEF，可能不需要Full Enc mode
        # 但修改配置通常需要
        
        print("认证成功")
        self.cmd_counter = 0
        # 注意：实际会话密钥生成比较复杂，这里暂略
        # 如果需要修改密钥或FileSettings，必须实现完整的 Session Key 生成

    def configure_sun_message(self, base_url, new_key):
        """
        配置 SUN (Secure Unique NFC)
        
        步骤:
        1. 更改文件设置 (FileSettings) 以启用 SDM (Secure Dynamic Messaging)
        2. 设置读取权限
        3. 写入 NDEF 消息模板
        """
        # 注意：这需要完整的 EV2 安全通信实现（CMAC计算，数据加密）
        # 这是一个非常底层的过程。
        
        print(">>> 警告 <<<")
        print("完整的 NTAG 424 DNA 配置需要复杂的 AES-CMAC 会话密钥计算。")
        print("此脚本目前仅作为框架。要真正写入，建议使用以下两种方式之一：")
        print("1. 使用 NXP 官方 Android App 'NXP TagWriter' (推荐开发初期使用)")
        print("2. 使用完整的 Python 库，如 'libfreefare' 的 Python 绑定，或者完善本脚本的 Crypto 部分。")
        print("")
        print(f"目标配置:")
        print(f"- 密钥: {binascii.hexlify(new_key).decode()}")
        print(f"- URL: {base_url}?d=0000... (PICC Data)")
        
        # 这里模拟一个写入 NDEF 的过程 (普通 NDEF，非 SUN)
        # 仅作演示连接性
        payload = b'\x00' # 占位
        print("硬件连接测试完成。")

    def run_demo(self):
        try:
            self.connect()
            self.select_application()
            
            # 默认使用 Key 0 认证
            self.authenticate_ev2_first(0, DEFAULT_KEY)
            
            print("\n=== 准备写入 ===")
            print("注意：这是演示脚本。实际启用 SUN 功能需要通过加密通道写入配置。")
            
            # 这里的逻辑在实际项目中需要替换为完整的 SDM 配置指令
            # 包含：
            # 1. ChangeKey (修改 Key 0, 1, 2)
            # 2. ChangeFileSettings (File 02 - NDEF 文件)
            #    - 设置 SDMEnabled = true
            #    - 设置 SDMOptions (UID Mirror, ReadCtr Mirror)
            #    - 设置 SDMAccessRights (Read=Key1/Free, Write=Key0)
            
        except Exception as e:
            print(f"\n❌ 错误: {e}")
        finally:
            if self.connection:
                self.connection.disconnect()

if __name__ == "__main__":
    writer = Ntag424Writer()
    writer.run_demo()
