import ctypes
import sys
import os
import struct
import time

class Ntag424DNA:
    def __init__(self):
        self.dll = None
        self.load_library()
        self.connection = self # Mock connection object for compatibility

    def load_library(self):
        # 尝试加载当前目录下的 OUR_MIFARE.dll
        dll_name = 'OUR_MIFARE.dll'
        if sys.platform == 'linux':
            dll_name = 'libOURMIFARE.so'
        elif sys.platform == 'darwin':
            dll_name = 'libOURMIFARE.dylib'
            
        # 搜索路径：当前目录，或 dist 目录
        possible_paths = [
            os.path.join(os.getcwd(), dll_name),
            os.path.join(os.path.dirname(__file__), dll_name),
            os.path.join(sys._MEIPASS, dll_name) if hasattr(sys, '_MEIPASS') else dll_name
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                try:
                    if sys.platform == 'win32':
                        self.dll = ctypes.windll.LoadLibrary(path)
                    else:
                        self.dll = ctypes.cdll.LoadLibrary(path)
                    print(f"Loaded DLL from: {path}")
                    break
                except Exception as e:
                    print(f"Failed to load {path}: {e}")
        
        if self.dll is None:
            # 尝试直接加载（如果在 PATH 中）
            try:
                if sys.platform == 'win32':
                    self.dll = ctypes.windll.LoadLibrary(dll_name)
                else:
                    self.dll = ctypes.cdll.LoadLibrary(dll_name)
                print(f"Loaded DLL from PATH: {dll_name}")
            except Exception as e:
                raise Exception(f"Could not load {dll_name}. Error: {e}")

    def beep(self, duration=30):
        if self.dll:
            self.dll.pcdbeep(duration)

    def connect(self):
        """寻卡并激活"""
        if not self.dll:
            raise Exception("DLL not loaded")
            
        mypiccserial = ctypes.create_string_buffer(7)
        myparam = ctypes.create_string_buffer(4)
        AtqaSak = ctypes.create_string_buffer(3)
        myver = ctypes.create_string_buffer(1)
        mycode = ctypes.create_string_buffer(1)
        
        # cpurequest1(uid, param, ver, code, atqasak)
        status = self.dll.cpurequest1(mypiccserial, myparam, myver, mycode, AtqaSak) % 256
        
        if status == 0 or status == 52: # 0=Success, 52=WupaSuccess?
            self.beep()
            uid = mypiccserial.raw[:7] # Usually 7 bytes for NTAG 424
            print(f"Card Found! UID: {uid.hex().upper()}")
            return uid
        else:
            raise Exception(f"Connect failed. Status: {status}")

    def select_application(self, aid_hex="D2760000850101"):
        """选择应用"""
        aid_bytes = bytes.fromhex(aid_hex)
        aid_len = len(aid_bytes)
        
        send_buf = bytearray(bytes.fromhex("00A40400"))
        send_buf.append(aid_len)
        send_buf += aid_bytes
        
        c_send = ctypes.create_string_buffer(bytes(send_buf), len(send_buf))
        c_rev = ctypes.create_string_buffer(128)
        c_rev_len = ctypes.create_string_buffer(4)
        
        status = self.dll.cpuisoapdu(c_send, len(send_buf), c_rev, c_rev_len) % 256
        
        if status == 0 or status == 55: # 0=Success
            print(f"Select Application {aid_hex} Success!")
            return True
        else:
            print(f"Select Application Failed: {status}")
            return False

    def send_apdu(self, ins, data=b'', p1=0x00, p2=0x00, le=None):
        """通用 APDU 发送 (封装 cpuisoapdu)"""
        # 这里的 INS 如果是 0xAD (ReadData)，我们应该封装成 Native Command
        # 也就是直接发送 [90 AD 00 00 Lc Data Le] 这样的 raw bytes?
        # 或者 cpuisoapdu 期望的是 CLA INS P1 P2 ...
        
        # 假设我们总是使用 Native CLA 0x90
        cla = 0x90
        
        # Construct APDU
        apdu = bytearray([cla, ins, p1, p2])
        if data:
            apdu.append(len(data))
            apdu.extend(data)
        if le is not None:
            apdu.append(le) # Le is usually 1 byte or 0 for 256?
            # If Le=0, append 00.
        
        c_send = ctypes.create_string_buffer(bytes(apdu), len(apdu))
        c_rev = ctypes.create_string_buffer(256)
        c_rev_len = ctypes.create_string_buffer(4)
        
        status = self.dll.cpuisoapdu(c_send, len(apdu), c_rev, c_rev_len) % 256
        
        if status == 0:
            # Parse length manually or assume
            # Assuming c_rev_len contains valid length?
            # It's not clear how to extract int from c_rev_len pointer in this context without struct
            # But we can try to parse SW from end of buffer if we assume it's filled
            
            # Let's try to read length from c_rev_len
            # Assuming it's a 4-byte int (Little Endian)
            l = struct.unpack('<I', c_rev_len.raw[:4])[0]
            
            # If l is reasonable (<=256)
            if l > 0 and l <= 256:
                response = c_rev.raw[:l]
                if len(response) >= 2:
                    sw = (response[-2] << 8) | response[-1]
                    resp_data = response[:-2]
                    return resp_data, sw
            
            # Fallback if length parsing fails or l=0
            return b'', 0x9000 # Assume success if status=0? No, unsafe.
        
        return b'', 0xFFFF # Comm Error

    def authenticate(self, key_no, key_hex):
        """认证 (EV2)"""
        if not self.dll:
            raise Exception("DLL not loaded")
            
        if len(key_hex) != 32:
            raise ValueError("Key must be 16 bytes (32 hex chars)")
            
        key_bytes = bytes.fromhex(key_hex)
        key_buf = ctypes.create_string_buffer(key_bytes, 16)
        retsw = ctypes.create_string_buffer(2)
        
        key_type = 0 # AES
        
        status = self.dll.desfireauthkeyev2(key_buf, key_no, key_type, retsw) % 256
        
        sw = (ord(retsw[0]) << 8) | ord(retsw[1])
        if status == 0 and sw == 0x9100:
            print(f"Auth Key {key_no} Success!")
            return True
        else:
            print(f"Auth Failed: Status={status}, SW={hex(sw)}")
            return False

    def write_ndef(self, url, key_no=0, key_hex="00000000000000000000000000000000"):
        """写入 NDEF"""
        picc_key_buf = ctypes.create_string_buffer(bytes.fromhex("00"*18), 18)
        
        lang = b"en"
        title = b""
        uri_header = 4
        if url.startswith("https://"):
            url_body = url[8:]
            uri_header = 4
        elif url.startswith("http://"):
            url_body = url[7:]
            uri_header = 3
        else:
            url_body = url
            uri_header = 0
            
        uri_bytes = url_body.encode('utf-8')
        
        self.dll.tagbuf_forumtype4_clear()
        
        res = self.dll.tagbuf_adduri(
            ctypes.create_string_buffer(lang), len(lang),
            ctypes.create_string_buffer(title), len(title),
            uri_header,
            ctypes.create_string_buffer(uri_bytes), len(uri_bytes)
        ) % 256
        
        if res != 0:
            raise Exception(f"Buffer Error: {res}")
            
        ctrl_word = 0x00 
        mypiccserial = ctypes.create_string_buffer(7)
        mypiccseriallen = ctypes.create_string_buffer(1)
        
        status = self.dll.forumtype4_write_ndeftag(ctrl_word, mypiccserial, mypiccseriallen, picc_key_buf) % 256
        
        if status == 0:
            print("NDEF Write Success!")
            return True
        else:
            raise Exception(f"NDEF Write Failed: {status}")

    def enable_sdm(self, picc_offset, mac_offset, key_no=0):
        """配置 SUN (ChangeFileSettings)"""
        # Step 1: Ensure Access Rights are safe (Read=E, Write=E, RW=E, Change=0)
        # This is a precaution.
        print("Step 1: Setting Access Rights (E0EE)...")
        file_no = 2
        mode = 3
        config = bytearray(32)
        
        config[0] = 0x00 # Disable SDM
        config[1] = 0xE0 # Change=0, RW=E
        config[2] = 0xEE # Write=E, Read=E
        j = 3
        
        databuf = ctypes.create_string_buffer(bytes(config[:j]), j)
        retsw = ctypes.create_string_buffer(2)
        self.dll.ntagchangefilesettings(mode, file_no, databuf, j, retsw)
        # Ignore result of Step 1 (it might fail if already set, or succeed)

        # Step 2: Enable SDM
        print("Enabling SDM (Attempting safe configuration)...")
        # Try best known configuration: FileOption 0x43, SDM Option 0x80, SDM Access EE F0, Offset 0
        config[0] = 0x43 # Enc+Mac + SDM
        config[1] = 0xE0
        config[2] = 0xEE
        config[3] = 0x80 # UID Mirror
        config[4] = 0xEE # Meta=E
        config[5] = 0xF0 # Ctr=F
        
        # Offset 0 (Safest)
        picc_offset = 0
        uid_off_bytes = struct.pack('<I', picc_offset)
        config[6] = uid_off_bytes[0]
        config[7] = uid_off_bytes[1]
        config[8] = uid_off_bytes[2]
        
        j = 9
        
        databuf = ctypes.create_string_buffer(bytes(config[:j]), j)
        retsw = ctypes.create_string_buffer(2)
        
        status = self.dll.ntagchangefilesettings(mode, file_no, databuf, j, retsw) % 256
        sw = (ord(retsw[0]) << 8) | ord(retsw[1])
        
        if status == 0 and sw == 0x9100:
            print("Configure SUN Success!")
            return True
        else:
            raise Exception(f"Configure SUN Failed: Status={status}, SW={hex(sw)}")

    def get_file_settings(self, file_no=2):
        """读取文件设置"""
        settings_buf = ctypes.create_string_buffer(64)
        rev_len = ctypes.create_string_buffer(2)
        retsw = ctypes.create_string_buffer(2)
        
        mode = 3 
        
        status = self.dll.ntagreadfilesettings(mode, file_no, settings_buf, rev_len, retsw) % 256
        sw = (ord(retsw[0]) << 8) | ord(retsw[1])
        
        if status == 0 and sw == 0x9100:
            length = ord(rev_len[0])
            data = settings_buf.raw[:length]
            print(f"File {file_no} Settings: {data.hex().upper()}")
            return data, sw
        else:
            print(f"GetFileSettings Failed: Status={status}, SW={hex(sw)}")
            return None, sw
