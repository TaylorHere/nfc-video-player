#!/usr/bin/env python3
from ntag424_manager import Ntag424DNA

def main():
    tag = Ntag424DNA()
    try:
        tag.connect()
        
        # 1. 认证 (默认全0密钥)
        try:
            tag.authenticate(0, "00000000000000000000000000000000")
            print("✓ 默认密钥认证成功")
        except Exception as e:
            print(f"⚠ 默认密钥认证失败: {e}")
            print("  (可能卡片已设置非默认密钥，或者之前的操作导致密钥状态改变)")

        # 2. 读取 NDEF
        print("-" * 30)
        print("尝试读取 NDEF (循环3次，检查 SDM 动态变化)...")
        for i in range(3):
            try:
                # ReadData: 90 AD 00 00 07 [FileNo] [Offset(3)] [Len(3)] 00
                # FileNo=02, Offset=0, Len=100
                data_header = bytes([0x02, 0x00, 0x00, 0x00, 0x64, 0x00, 0x00])
                resp, sw = tag.send_apdu(0xAD, data=data_header)
                
                resp_bytes = bytes(resp)
                if sw == 0x9000 or sw == 0x9100:
                    length = (resp_bytes[0] << 8) | resp_bytes[1]
                    if length > 0:
                        content = resp_bytes[2:2+length]
                        # 尝试找到 URL
                        try:
                            # 简单的查找
                            s_content = content.decode('utf-8', errors='ignore')
                            start = s_content.find('http')
                            if start != -1:
                                url = s_content[start:]
                                print(f"[{i+1}] URL: {url}")
                            else:
                                print(f"[{i+1}] Raw: {content.hex().upper()}")
                        except:
                            print(f"[{i+1}] Raw: {content.hex().upper()}")
                    else:
                        print(f"[{i+1}] 空 NDEF 文件")
                else:
                    print(f"[{i+1}] 读取失败: {hex(sw)}")
            except Exception as e:
                print(f"[{i+1}] 读取异常: {e}")
        
        print("-" * 30)

        # 3. 获取文件设置 (FileSettings)
        try:
            # GetFileSettings: 90 F5 00 00 01 [FileNo] 00
            resp, sw = tag.send_apdu(0xF5, data=bytes([0x02]))
            if sw == 0x9000 or sw == 0x9100:
                settings = bytes(resp)
                file_type = settings[0]
                file_option = settings[1]
                access_rights = settings[2:4]
                print(f"✓ 文件设置 (File 02):")
                print(f"  Type: {hex(file_type)}")
                print(f"  Option: {hex(file_option)} (Bit 6=SDMEnabled?)")
                print(f"  Access: {access_rights.hex()}")
                if len(settings) > 4:
                    print(f"  SDM Config: {settings[4:].hex().upper()}")
            else:
                print(f"✗ 获取设置失败: {hex(sw)}")
        except Exception as e:
            print(f"✗ 获取设置出错: {e}")

    except Exception as e:
        print(f"❌ 连接失败: {e}")

if __name__ == "__main__":
    main()
