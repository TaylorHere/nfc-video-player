#!/usr/bin/env python3
"""系统探测 MagTek IC-02 / OUR_MIFARE 协议"""
import hid
import time

def xh_checksum(data):
    chk = 0
    for b in data:
        chk ^= b
    return chk

def send_cmd(h, cmd_code, data=[], rid=0x00):
    pkt = [0x78, 0x68, len(data)+1, cmd_code] + data
    pkt.append(xh_checksum(pkt))
    
    buf = [rid] + pkt + [0]*(64-len(pkt))
    h.write(buf)
    time.sleep(0.05)
    return h.read(64, timeout_ms=200)

def main():
    h = hid.device()
    h.open(0x0801, 0x2011)
    
    print("=== 系统探测 MagTek IC-02 ===\n")
    
    # 常见命令码探测
    cmds = {
        0x01: "Beep",
        0x02: "Get Version",
        0x03: "Get Serial",
        0x10: "RF Field On",
        0x11: "Request Card (REQA)",
        0x12: "Anticollision",
        0x13: "Select Card",
        0x14: "Halt",
        0x15: "Auth Key A",
        0x16: "Auth Key B",
        0x17: "Read Block",
        0x18: "Write Block",
        0x20: "ISO14443-4 RATS",
        0x21: "ISO14443-4 PPS",
        0x22: "ISO14443-4 APDU",
        0x30: "Mifare Read",
        0x31: "Mifare Write",
        0x40: "DESFire Auth",
        0x41: "DESFire Cmd",
    }
    
    print("探测命令响应 (RID=0x00):")
    for cmd, name in cmds.items():
        res = send_cmd(h, cmd)
        if res:
            # 解析响应
            if res[0] == 0x78 and res[1] == 0x68:
                rlen = res[2]
                rcode = res[3] if rlen > 0 else None
                code_str = f"0x{rcode:02X}" if rcode is not None else "N/A"
                print(f"  Cmd 0x{cmd:02X} ({name}): len={rlen}, code={code_str}, raw={bytes(res[:8]).hex()}")
            else:
                print(f"  Cmd 0x{cmd:02X} ({name}): {bytes(res[:16]).hex()}")
    
    print("\n探测 Beep 变体:")
    # 尝试不同的 Beep 参数
    for dur in [10, 30, 50, 100]:
        res = send_cmd(h, 0x01, [dur])
        if res:
            print(f"  Beep({dur}): {bytes(res[:8]).hex()}")
    
    print("\n尝试寻卡命令 (请将卡放在读卡器上):")
    # ISO14443A Request: 0x26 (REQA) or 0x52 (WUPA)
    for req_type in [0x26, 0x52]:
        res = send_cmd(h, 0x11, [req_type])
        if res:
            print(f"  Request(0x{req_type:02X}): {bytes(res[:16]).hex()}")
    
    h.close()
    print("\n完成!")

if __name__ == "__main__":
    main()
