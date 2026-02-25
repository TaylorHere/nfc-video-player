import hid

def probe_magtek_details():
    VENDOR_ID = 0x0801
    PRODUCT_ID = 0x2011
    
    print(f"正在深入探测 MagTek IC-02...")
    try:
        # 寻找所有匹配的设备接口
        infos = hid.enumerate(VENDOR_ID, PRODUCT_ID)
        if not infos:
            print("未找到设备")
            return

        for info in infos:
            print(f"\n--- 发现接口 ---")
            print(f"路径: {info['path']}")
            print(f"制造商: {info['manufacturer_string']}")
            print(f"产品: {info['product_string']}")
            print(f"接口编号: {info['interface_number']}")
            print(f"使用类型 (Usage Page): {hex(info['usage_page'])}")
            print(f"使用 ID (Usage): {hex(info['usage'])}")

    except Exception as e:
        print(f"探测失败: {e}")

if __name__ == "__main__":
    probe_magtek_details()
