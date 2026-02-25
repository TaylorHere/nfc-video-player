import hid
import time

class MagTekTransport:
    def __init__(self, vid=0x0801, pid=0x2011):
        self.h = hid.device()
        self.h.open(vid, pid)
        self.h.set_nonblocking(False)
        
    def xh_checksum(self, data):
        chk = 0
        for b in data:
            chk ^= b
        return chk

    def send_cmd(self, cmd_code, data=[]):
        pkt = [0x78, 0x68, len(data)+1, cmd_code] + data
        pkt.append(self.xh_checksum(pkt))
        buf = [0x00] + pkt + [0]*(64-len(pkt))
        self.h.write(buf)
        res = self.h.read(64, timeout_ms=1000)
        if not res: return None
        return list(res)

    def connect_card(self):
        # Search
        res = self.send_cmd(0x10)
        if not res or res[4] != 0x00: return False
        # RATS
        res = self.send_cmd(0x20)
        if not res or res[4] != 0x00: return False
        return True

    def send_apdu(self, apdu):
        # Cmd 0x22 is APDU
        res = self.send_cmd(0x22, list(apdu))
        if not res: return None
        if res[4] == 0x00:
            # Data starts at index 5, length is res[2]-1
            payload = bytes(res[5:5+res[2]-1])
            return payload
        else:
            print(f"APDU Status Error: 0x{res[4]:02X}")
            return None

    def close(self):
        self.h.close()
