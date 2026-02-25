import hid
import time

def scan_magtek():
    VENDOR_ID = 0x0801
    PRODUCT_ID = 0x2011
    
    try:
        h = hid.device()
        h.open(VENDOR_ID, PRODUCT_ID)
        h.set_nonblocking(True)
        
        # 尝试几种常见的 MagTek 命令格式
        commands = [
            [0x01, 0x01, 0x01], # 常见的 Get Version 或 Status
            [0x02, 0x01, 0x01],
            [0x01, 0x00, 0x01, 0x03], # 尝试 Beep
        ]
        
        for cmd in commands:
            # 补全到 64 字节 (MagTek 通常使用 64 字节固定长度报文)
            buf = [0] * 65
            for i, b in enumerate(cmd):
                buf[i+1] = b
            
            print(f"发送测试命令: {bytes(cmd).hex()}")
            h.write(buf)
            
            # 等待响应
            time.sleep(0.1)
            d = h.read(64)
            if d:
                print(f"收到响应: {bytes(d).hex()}")
            else:
                print("无响应")
                
        h.close()
    except Exception as e:
        print(f"错误: {e}")

if __name__ == "__main__":
    scan_magtek()
