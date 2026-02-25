import hid
import time

def xh_checksum(data):
    chk = 0
    for b in data:
        chk ^= b
    return chk

def main():
    VENDOR_ID = 0x0801
    PRODUCT_ID = 0x2011
    
    infos = hid.enumerate(VENDOR_ID, PRODUCT_ID)
    if not infos:
        print("未找到设备")
        return
    
    path = infos[0]['path']
    print(f"Connecting to {path}")
    
    try:
        h = hid.device()
        h.open_path(path)
        
        # 探测 Report ID 0x01
        # MagTek IC-02 通常使用 Report ID 0x01 为发送，0x01 或 0x02 为接收
        
        # 尝试让设备返回一些东西
        # 很多这类设备在空闲时会循环发送 78 68 ...
        
        print("Listening for 1 second...")
        start = time.time()
        while time.time() - start < 1.0:
            d = h.read(64, timeout_ms=100)
            if d:
                print(f"Async Data: {bytes(d).hex()}")
        
        # 发送 Beep (尝试不同的格式)
        cmds = [
            [0x78, 0x68, 0x01, 0x01, 0x10], # Header, Header, Len, Cmd, Sum
            [0x01, 0x00, 0x01, 0x03],       # MagTek Standard Beep
        ]
        
        for pkt in cmds:
            buf = [0] * 65
            buf[0] = 0x01 # Report ID 1
            for i, b in enumerate(pkt):
                buf[i+1] = b
            
            print(f"Sending: {bytes(pkt).hex()}")
            h.write(buf)
            time.sleep(0.1)
            d = h.read(64, timeout_ms=200)
            if d:
                print(f"Response: {bytes(d).hex()}")
                
        h.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
