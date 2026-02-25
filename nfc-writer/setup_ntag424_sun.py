#!/usr/bin/env python3
from ntag424_manager import Ntag424DNA

# 核心密钥配置
K0_MASTER = "D5A60346701B67C6A28B894B725DC23B"

def main():
    tag = Ntag424DNA()
    try:
        tag.connect()
        
        # 1. 认证 (默认全0密钥)
        print("正在尝试默认密钥认证...")
        tag.authenticate(0, "00000000000000000000000000000000")
        
        # 2. 写入 NDEF
        url = "https://deo.app/nfc?p=00000000000000000000000000000000&m=0000000000000000"
        tag.write_ndef(url)
        
        # 3. 开启 SDM 动态镜像
        # Calculated Offsets:
        # FileHeader(2) + NDEFMsgHeader(5) = 7 bytes prefix.
        # "https://deo.app/nfc?p=" is 22 chars.
        # p starts at 7 + 22 = 29.
        # p length = 32.
        # "&m=" is 3 chars.
        # m starts at 29 + 32 + 3 = 64.
        tag.setup_sdm(picc_offset=29, mac_offset=64)
        
        print("\n" + "="*40)
        print("✓ 卡片配置成功！已开启动态防伪。")
        print("="*40)
        
    except Exception as e:
        print(f"\n❌ 执行失败: {e}")

if __name__ == "__main__":
    main()
