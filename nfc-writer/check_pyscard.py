import sys
try:
    from smartcard.System import readers
    from smartcard.util import toHexString
    
    r = readers()
    print(f"Readers found: {r}")
    if len(r) > 0:
        connection = r[0].createConnection()
        connection.connect()
        print(f"Connected to: {r[0]}")
        # Get UID
        cmd = [0xFF, 0xCA, 0x00, 0x00, 0x00]
        data, sw1, sw2 = connection.transmit(cmd)
        print(f"UID: {toHexString(data)} SW={hex(sw1)} {hex(sw2)}")
except ImportError:
    print("pyscard not installed")
except Exception as e:
    print(f"Error: {e}")
