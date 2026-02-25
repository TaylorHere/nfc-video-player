import hid
import time

def test_magtek():
    # MagTek IC-02 标识
    VENDOR_ID = 0x0801
    PRODUCT_ID = 0x2011

    print(f"正在尝试连接 MagTek IC-02 (ID: {hex(VENDOR_ID)}:{hex(PRODUCT_ID)})...")
    
    try:
        # 1. 寻找设备
        device = hid.device()
        device.open(VENDOR_ID, PRODUCT_ID)
        print("✓ 成功连接到 MagTek 硬件！")

        # 2. 发送一个简单的 Beep 指令 (MagTek HID 格式)
        # 注意: MagTek 指令通常以 Report ID 0x01 或 0x02 开头
        # 下面是一个典型的 Beep 指令尝试
        # 指令长度通常需要对齐到 64 字节
        beep_cmd = [0x00] * 65
        beep_cmd[1] = 0x01 # 指令标识
        beep_cmd[2] = 0x03 # Beep 操作
        
        print("尝试让读卡器响一声...")
        device.write(beep_cmd)
        
        time.sleep(0.5)
        device.close()
        print("测试完成。")

    except Exception as e:
        print(f"❌ 硬件操作失败: {e}")
        print("\n提示: 如果报 'Access Denied'，请尝试运行: sudo chmod 666 /dev/hidraw*")

if __name__ == "__main__":
    test_magtek()
