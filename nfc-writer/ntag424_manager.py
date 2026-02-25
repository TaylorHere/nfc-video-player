#!/usr/bin/env python3
"""
NTAG 424 DNA Pure Python Implementation (EV2 Protocol)
不需要外部 .so 库，直接使用 pyscard 和 pycryptodome。
"""

import os
import struct
from smartcard.System import readers
from smartcard.util import toHexString, toBytes
from Crypto.Cipher import AES
from Crypto.Hash import CMAC
from Crypto.Random import get_random_bytes
from Crypto.Util import Counter

class Ntag424DNA:
    # 命令字
    CMD_AUTHENTICATE_EV2_FIRST = 0x71
    CMD_CHANGE_FILE_SETTINGS = 0x5F
    CMD_WRITE_DATA = 0x8D
    
    def __init__(self):
        self.connection = None
        self.reader = None
        self.ti = None
        self.key_enc = None
        self.key_mac = None
        self.cmd_counter = 0

    def connect(self):
        r = readers()
        if not r:
            raise Exception("No NFC reader found")
        self.reader = r[0]
        self.connection = self.reader.createConnection()
        self.connection.connect()
        print(f"✓ Connected to {self.reader}")
        self.select_application("D2760000850101")

    def select_application(self, aid_hex):
        aid = bytes.fromhex(aid_hex)
        apdu = [0x00, 0xA4, 0x04, 0x00, len(aid)] + list(aid)
        resp, sw1, sw2 = self.connection.transmit(apdu)
        sw = (sw1 << 8) | sw2
        if sw != 0x9000:
            if aid_hex == "D2760000850101":
                self.select_application("D2760000850100")
            else:
                raise Exception(f"Failed to select application: {hex(sw)}")
        else:
            print(f"✓ Selected AID: {aid_hex}")

    def send_apdu(self, ins, data=b""):
        header = [0x90, ins, 0x00, 0x00]
        apdu = header + [len(data)] + list(data) + [0x00]
        resp, sw1, sw2 = self.connection.transmit(apdu)
        return resp, (sw1 << 8 | sw2)

    def rotate_left(self, data):
        return data[1:] + data[:1]

    def _generate_session_keys(self, rnd_a, rnd_b, ti, key):
        sv_mac = bytearray([0x01, 0x54, 0x49]) + ti + bytes([rnd_a[14]^rnd_b[14], rnd_a[15]^rnd_b[15]]) + b'\x00' * 7
        c_mac = CMAC.new(key, ciphermod=AES)
        c_mac.update(sv_mac)
        self.key_mac = c_mac.digest()
        print(f"✓ Session Keys generated (MAC): {self.key_mac.hex().upper()}")

    def calculate_cmac(self, cmd, data=b""):
        msg = bytes([cmd]) + self.cmd_counter.to_bytes(2, 'little') + self.ti + data
        c = CMAC.new(self.key_mac, ciphermod=AES)
        c.update(msg)
        return c.digest()[:8]

    def authenticate(self, key_no, key_hex):
        key = bytes.fromhex(key_hex)
        print(f"Authenticating with Key {key_no}...")
        
        # Part 1
        resp, sw = self.send_apdu(self.CMD_AUTHENTICATE_EV2_FIRST, data=bytes([key_no, 0x00]))
        if sw != 0x91AF: raise Exception(f"Auth Part 1 Failed: {hex(sw)}")
        
        rnd_b_enc = bytes(resp)
        iv = bytes(16)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        rnd_b = cipher.decrypt(rnd_b_enc)
        
        # Part 2
        rnd_a = get_random_bytes(16)
        rnd_b_prime = self.rotate_left(rnd_b)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        token = cipher.encrypt(rnd_a + rnd_b_prime)
        
        resp, sw = self.send_apdu(0xAF, data=token)
        if sw != 0x9000 and sw != 0x9100: raise Exception(f"Auth Part 2 Failed: {hex(sw)}")
        
        resp_bytes = bytes(resp)
        self.ti = resp_bytes[:4]
        self._generate_session_keys(rnd_a, rnd_b, self.ti, key)
        self.cmd_counter = 0
        return True

    def setup_sdm(self, picc_offset, mac_offset):
        """
        开启 Encrypted File Data 模式 (SDMOptions=0x11)
        """
        print(f"Configuring SDM (Offsets: P={picc_offset}, M={mac_offset})...")
        
        # Cmd 0x5F (ChangeFileSettings) Payload
        data = bytearray()
        data.append(0x40)          # FileOption: SDM Enabled
        data.append(0xE0)          # AccessRights: Read=Free, Write=Key0
        data.append(0x00)          # AccessRights: RW=Key0, Change=Key0
        
        # SDM Options: EncFileData (0x10) | ASCII (0x01)
        data.append(0x11)          
        
        # SDM Access Rights
        data.append(0xF0)          # CtrRet=Key0 (Nibble 0)
        data.append(0xE0)          # MetaRead=Free (Nibble 1), FileRead=Key0 (Nibble 0) -> 0xE0
        # Wait, if FileRead=Key0 (0), then MAC/Enc is enabled.
        # If FileRead=E (Free), MAC/Enc is disabled?
        # Code: if (configdata[5] & 0x0F) != 0x0F: ... (means MAC Key is set)
        # We set it to 0 (Key 0). Correct.
        
        # Offsets (3 bytes each)
        # 1. SDMMACInputOffset (Start of MAC calculation - 0)
        data += struct.pack("<I", 0)[:3]
        
        # 2. SDMENCOffset (Start of Encrypted Data - 'p=' value)
        data += struct.pack("<I", picc_offset)[:3]
        
        # 3. SDMENCLength (Length of data to encrypt - 32 bytes)
        data += struct.pack("<I", 32)[:3]
        
        # 4. SDMMACOffset (Start of MAC - 'm=' value)
        data += struct.pack("<I", mac_offset)[:3]
        
        # Total Offsets: 4 (12 bytes)
        # Total Payload: 1+2+1+2+12 = 18 bytes.
        
        self.cmd_counter += 1
        full_data_for_mac = bytes([0x02]) + data
        mac = self.calculate_cmac(self.CMD_CHANGE_FILE_SETTINGS, full_data_for_mac)
        
        final_apdu_data = full_data_for_mac + mac
        
        resp, sw = self.send_apdu(self.CMD_CHANGE_FILE_SETTINGS, data=final_apdu_data)
        
        if sw == 0x9000:
            print("✓ SDM successfully enabled!")
            return True
        else:
            print(f"✗ SDM configuration failed: {hex(sw)}")
            return False

    def write_ndef(self, url):
        print(f"Writing NDEF URL: {url}")
        prefix = 0x00 
        payload = bytes([prefix]) + url.encode('utf-8')
        ndef_msg = bytes([0xD1, 0x01, len(payload), 0x55]) + payload
        file_data = struct.pack(">H", len(ndef_msg)) + ndef_msg
        
        header = bytes([0x02, 0x00, 0x00, 0x00]) + struct.pack("<I", len(file_data))[:3]
        full_apdu = header + file_data
        
        print(f"Sending WriteData (Plain, {len(full_apdu)} bytes)...")
        resp, sw = self.send_apdu(self.CMD_WRITE_DATA, data=full_apdu)
        
        if sw == 0x9000 or sw == 0x9100:
            print("✓ NDEF written successfully!")
            return True
        else:
            print(f"✗ Write NDEF failed: {hex(sw)}")
            return False
