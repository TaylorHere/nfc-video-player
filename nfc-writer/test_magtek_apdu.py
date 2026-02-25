import hid
import time

def test_apdu_encapsulation():
    VENDOR_ID = 0x0801
    PRODUCT_ID = 0x2011
    
    # ISO Select NDEF Application: 00 A4 04 00 07 D2 76 00 00 85 01 01
    apdu = [0x00, 0xA4, 0x04, 0x00, 0x07, 0xD2, 0x76, 0x00, 0x00, 0x85, 0x01, 0x01]
    
    try:
        h = hid.device()
        h.open(VENDOR_ID, PRODUCT_ID)
        h.set_nonblocking(True)
        
        # 常见封装格式
        # 1. 直接封装: [ReportID] [Len] [APDU...]
        # 2. MagTek 通用封装: 02 00 [TotalLen L] [TotalLen H] [Cmd] [Data...]
        
        test_cmds = [
            [0x01, len(apdu)] + apdu,
            [0x02, 0x00, len(apdu)+1, 0x00, 0x25] + apdu, # 0x25 常用作 NFC 通讯
        ]
        
        for cmd in test_cmds:
            buf = [0] * 65
            for i, b in enumerate(cmd):
                buf[i+1] = b
            
            print(f"发送 APDU 封装: {bytes(cmd).hex()}")
            h.write(buf)
            
            time.sleep(0.2)
            d = h.read(64)
            if d:
                print(f"收到响应: {bytes(d).hex()}")
            else:
                print("无响应")
                
        h.close()
    except Exception as e:
        print(f"错误: {e}")

if __name__ == "__main__":
    test_apdu_encapsulation()
