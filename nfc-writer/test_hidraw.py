#!/usr/bin/env python3
import os
import time

def xh_checksum(data):
    chk = 0
    for b in data:
        chk ^= b
    return chk

def main():
    dev = "/dev/hidraw0"
    if not os.path.exists(dev):
        print(f"{dev} not found")
        return
        
    try:
        fd = os.open(dev, os.O_RDWR | os.O_NONBLOCK)
        print(f"Opened {dev}")
    except Exception as e:
        print(f"Open failed: {e}")
        return

    # 1. Search Card (0x10)
    # Header: 78 68, Len: 01, Cmd: 10, Sum: 01
    pkt = [0x78, 0x68, 0x01, 0x10, 0x01]
    # HID requires first byte to be 0x00 for RID 0
    buf = bytes([0x00] + pkt + [0]*(64-len(pkt)))
    
    os.write(fd, buf)
    time.sleep(0.1)
    
    try:
        res = os.read(fd, 64)
        print(f"Response (0x10): {res.hex().upper()}")
    except:
        print("No response from 0x10")
        
    # 2. Try Beep (0x01)
    pkt = [0x78, 0x68, 0x01, 0x01, 0x10]
    buf = bytes([0x00] + pkt + [0]*(64-len(pkt)))
    os.write(fd, buf)
    print("Sent Beep command via hidraw")
    
    os.close(fd)

if __name__ == "__main__":
    main()
