import struct
from ntag424_manager import Ntag424DNA

from Crypto.Hash import CMAC
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

class SDMTester(Ntag424DNA):
    CMD_GET_FILE_SETTINGS = 0xF5

    def __init__(self):
        super().__init__()
        
import struct
import sys
import os
import ctypes
from binascii import unhexlify
from smartcard.System import readers
from smartcard.util import toHexString

# ... (Imports) ...

class SDMTester(Ntag424DNA):
    CMD_GET_FILE_SETTINGS = 0xF5
    
    def probe_key_combinations(self):
        print("\n=== PROBING KEY COMBINATIONS ===")
        
        combinations = [
            ("Enc=k1, Mac=k2", lambda k1, k2, k0: (k1, k2)),
            ("Enc=k2, Mac=k1", lambda k1, k2, k0: (k2, k1)),
            ("Enc=k0, Mac=k1", lambda k1, k2, k0: (k0, k1)),
            ("Enc=k0, Mac=k2", lambda k1, k2, k0: (k0, k2)),
            ("Enc=k1, Mac=k0", lambda k1, k2, k0: (k1, k0)), # Unlikely
            ("Enc=k2, Mac=k0", lambda k1, k2, k0: (k2, k0)), # Unlikely
            ("Enc=k0, Mac=k0", lambda k1, k2, k0: (k0, k0)), # Fallback
        ]

        payload = bytes.fromhex("00 E0 00") # Minimal Change
        
        for name, key_func in combinations:
            print(f"\nTesting {name}...")
            try:
                # 1. Authenticate to get fresh session keys
                # We need to capture k1 and k2 from the auth process.
                # Since authenticate() sets self.key_enc/mac, we need to intercept or modify authenticate.
                # Let's modify _generate_session_keys to store k1/k2/k0 for us to use.
                self.authenticate(0, "00000000000000000000000000000000")
                
                # Now apply the combination
                k1 = self.last_k1
                k2 = self.last_k2
                k0 = bytes.fromhex("00000000000000000000000000000000")
                
                self.key_enc, self.key_mac = key_func(k1, k2, k0)
                
                # 2. Construct APDU
                full_data = bytes([0x02]) + payload
                enc_data = self.encrypt_data(full_data)
                
                self.cmd_counter += 1
                mac = self.calculate_cmac(self.CMD_CHANGE_FILE_SETTINGS, enc_data)
                
                final_apdu = enc_data + mac
                
                print(f"  Sending Disable SDM...")
                # Try sending without Le
                resp, sw = self.send_apdu(self.CMD_CHANGE_FILE_SETTINGS, data=final_apdu, le=None)
                print(f"  -> SW={hex(sw)}")
                
                if sw == 0x9000:
                    print(f"  ✅ SUCCESS! Valid Combination: {name}")
                    return # Stop if found
                elif sw == 0x911E:
                     print(f"  -> Integrity Error (MAC Wrong)")
                elif sw == 0x91AE:
                     print(f"  -> Auth Error (MAC Wrong)")
                elif sw == 0x91F0:
                     print(f"  -> File Not Found (Enc Wrong)")
                elif sw == 0x919E:
                     print(f"  -> Value Error (Enc Wrong OR Payload Bad)")
            except Exception as e:
                print(f"  Error: {e}")

    def _generate_session_keys(self, rnd_a, rnd_b, key):
        # Use DLL for KDF
        dll_name = os.path.abspath('OUR_MIFARE.dll')
        if not os.path.exists(dll_name):
            print("DLL not found")
            return

        try:
            if hasattr(os, 'add_dll_directory'):
                 os.add_dll_directory(os.path.dirname(dll_name))
            lib = ctypes.cdll.LoadLibrary(dll_name)
            
            # Prepare Inputs
            rnd_b_prime = rnd_b[1:] + rnd_b[:1]
            randdata = (ctypes.c_ubyte * 32)(*list(rnd_a + rnd_b_prime))
            key_buf = (ctypes.c_ubyte * 16)(*list(key))
            key_len = 16
            result_buf = (ctypes.c_ubyte * 32)()
            
            # Call cpucalcexauthkey
            lib.cpucalcexauthkey(ctypes.byref(randdata), ctypes.byref(key_buf), key_len, ctypes.byref(result_buf))
            
            res_bytes = bytes(result_buf)
            
            # Store raw keys for probing
            self.last_k1 = res_bytes[:16]
            self.last_k2 = res_bytes[16:]
            
            # Default to what we think is right (will be overridden by probe)
            self.key_enc = self.last_k1
            self.key_mac = self.last_k2

        except Exception as e:
            print(f"DLL KDF Failed: {e}")
            self.last_k1 = key
            self.last_k2 = key

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
        
        # TI is the first 4 bytes of RndB
        self.ti = rnd_b[:4]
        print(f"✓ TI Extracted from RndB: {self.ti.hex().upper()}")
        
        # Part 2
        rnd_a = get_random_bytes(16)
        rnd_b_prime = self.rotate_left(rnd_b)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        token = cipher.encrypt(rnd_a + rnd_b_prime)
        
        resp, sw = self.send_apdu(0xAF, data=token)
        if sw != 0x9000 and sw != 0x9100: raise Exception(f"Auth Part 2 Failed: {hex(sw)}")
        
        resp_bytes = bytes(resp)
        print(f"DEBUG: Auth Part 2 Resp Len={len(resp_bytes)}, Data={resp_bytes.hex()}")
        
        # Generate keys
        self._generate_session_keys(rnd_a, rnd_b, key)
        return True

    def encrypt_data(self, data, key=None):
        if key is None:
            key = self.key_enc
        # ISO 7816-4 Padding: 80 ... 00
        padded_data = bytearray(data)
        padded_data.append(0x80)
        while len(padded_data) % 16 != 0:
            padded_data.append(0x00)
        
        # IV is zero for each command in standard EV2?
        iv = bytes(16)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        return cipher.encrypt(bytes(padded_data))

    def probe_encryption_with_hypothesis(self):
        print("\n=== PROBING ENCRYPTION WITH HYPOTHESIS (01 54 45) ===")
        
        # Base Payload (Plain)
        # FileOpt(40) + AR(E0 00) + SDMOpt(81) + SDMAR(FF 0E) + UIDOffset(3) + MACOffset(3)
        # Length = 1+2+1+2+3+3 = 12 bytes.
        
        base_payload = bytes.fromhex("40 E0 00 81 FF 0E") + bytes([0x00, 0x00, 0x00]) + bytes([0x00, 0x00, 0x00]) # 12 bytes
        
        # Authenticate
        try:
            self.authenticate(0, "00000000000000000000000000000000")
        except:
            print("Auth failed")
            return

        self.cmd_counter += 1
        
        # 1. Encrypt Payload
        enc_data = self.encrypt_data(base_payload)
        print(f"  Plain Payload: {base_payload.hex()} (Len={len(base_payload)})")
        print(f"  Encrypted Payload: {enc_data.hex()} (Len={len(enc_data)})")
        
        # 2. Calculate MAC over Encrypted Data
        # Header + Ctr + TI + EncData
        full_data_for_mac = bytes([0x02]) + enc_data # FileNo + EncData ??
        # Wait. Is FileNo encrypted?
        # Usually FileNo is NOT encrypted in ChangeFileSettings?
        # Let's check.
        # Command 0x5F: FileNo (1 byte) + Data.
        # If CommMode.Full:
        #   CmdHeader = 5F [FileNo] ?
        #   No, CmdHeader is just 5F.
        #   Data = FileNo + Payload.
        #   EncryptedData = Enc(Data).
        #   So FileNo IS encrypted.
        
        # BUT, standard DESFire ChangeFileSettings takes FileNo as parameter.
        # If I encrypt FileNo, the card can't know which file to change until it decrypts.
        # This seems correct for "Confidential" mode.
        
        full_data_to_encrypt = bytes([0x02]) + base_payload
        enc_data = self.encrypt_data(full_data_to_encrypt)
        
        # MAC is calculated over: Cmd(1) + Ctr(2) + TI(4) + EncData(N)
        # Note: self.calculate_cmac adds Cmd + Ctr + TI.
        # So we pass EncData.
        mac = self.calculate_cmac(self.CMD_CHANGE_FILE_SETTINGS, enc_data)
        
        final_apdu = enc_data + mac # Wait, FileNo is inside EncData.
        
        print(f"  Sending Encrypted APDU (Len={len(final_apdu)})...")
        resp, sw = self.send_apdu(self.CMD_CHANGE_FILE_SETTINGS, data=final_apdu)
        
        if sw == 0x9000:
            print(f"  ✅ SUCCESS! Encryption worked!")
        else:
            print(f"  ❌ FAILED. SW={hex(sw)}")

    def get_file_settings(self, file_no):
        print(f"\n--- GetFileSettings (File {file_no}) ---")
        try:
            self.authenticate(0, "00000000000000000000000000000000")
            
            # GetFileSettings is 0xF5. 
            # In EV2, we can send it in Plain (if allowed) or Encrypted.
            # Let's try Plain first as it's easier.
            
            resp, sw = self.send_apdu(0xF5, bytes([file_no]))
            if sw == 0x9000:
                print(f"  ✅ Success (Plain)! Resp: {resp.hex()}")
                return resp
            else:
                print(f"  ❌ Failed (Plain). SW={hex(sw)}")
                
            # Try Encrypted/MAC'd if Plain failed?
            # Usually GetFileSettings is allowed in plain if AccessRights say so.
            return None
        except Exception as e:
            print(f"  ⚠️ Error: {e}")
            return None

    def probe_minimal_change(self):
        print("\n=== PROBING MINIMAL CHANGE ===")
        
        # Try different File Options
        # 00: Plain
        # 01: MAC
        # 03: Encrypted
        # 40: Plain + SDM (Current?)
        
        options = [0x00, 0x01, 0x03, 0x40]
        
        for opt in options:
            payload = bytes([opt]) + bytes.fromhex("E0 00")
            print(f"\nTesting FileOpt={hex(opt)} (Payload={payload.hex()})...")
            
            try:
                self.authenticate(0, "00000000000000000000000000000000")
                self.key_enc = self.last_k1
                self.key_mac = self.last_k2
            except: continue
            
            full_data = bytes([0x02]) + payload
            enc_data = self.encrypt_data(full_data)
            
            self.cmd_counter += 1
            mac = self.calculate_cmac(self.CMD_CHANGE_FILE_SETTINGS, enc_data)
            
            final_apdu = enc_data + mac
            
            resp, sw = self.send_apdu(self.CMD_CHANGE_FILE_SETTINGS, data=final_apdu, le=None)
            print(f"  -> SW={hex(sw)}")
            if sw == 0x9000:
                print(f"  ✅ SUCCESS with Opt={hex(opt)}!")
                return

    def probe_lengths(self):
        print("\n=== PROBING LENGTHS FOR 0x81 (UID + MAC) ===")
        # Base Payload: FileOpt(40) + AR(E0 00) + SDMOpt(81) + SDMAR(EE 0E)
        # Note: Using fixed SDMAR (EE 0E)
        base_payload = bytes.fromhex("40 E0 00 81 EE 0E")
        
        # We test different number of offsets (each offset is 3 bytes)
        for num_offsets in range(0, 5): 
            padding = b'\x00' * (num_offsets * 3)
            data = bytearray(base_payload + padding)
            
            try:
                self.authenticate(0, "00000000000000000000000000000000")
            except:
                print("Auth failed")
                continue
            
            # Encrypt: FileNo + Data
            full_data_to_encrypt = bytes([0x02]) + data
            enc_data = self.encrypt_data(full_data_to_encrypt)
            
            # MAC over EncData
            self.cmd_counter += 1
            mac = self.calculate_cmac(self.CMD_CHANGE_FILE_SETTINGS, enc_data)
            
            final_apdu = enc_data + mac
            
            print(f"Testing Length {len(data)} (Offsets={num_offsets})...")
            try:
                resp, sw = self.send_apdu(self.CMD_CHANGE_FILE_SETTINGS, data=final_apdu)
                print(f"  -> SW={hex(sw)}")
                if sw == 0x9000:
                    print(f"  ✅ FOUND VALID CONFIG: {num_offsets} Offsets (Len={len(data)})")
            except Exception as e:
                print(f"  -> Error: {e}")

    def probe_minimal_sdm(self):
        print("\n=== PROBING MINIMAL SDM (0x80 - Binary UID) ===")
        # FileOpt(40) + AR(E0 00) + SDMOpt(80) + SDMAR(EE 0E) + UIDOff(3)
        # Total = 9 bytes
        payload = bytes.fromhex("40 E0 00 80 EE 0E") + struct.pack("<I", 32)[:3]
        
        try:
            self.authenticate(0, "00000000000000000000000000000000")
        except: return
        
        full_data = bytes([0x02]) + payload
        enc_data = self.encrypt_data(full_data)
        
        self.cmd_counter += 1
        mac = self.calculate_cmac(self.CMD_CHANGE_FILE_SETTINGS, enc_data)
        
        final_apdu = enc_data + mac
        
        print(f"Sending SDM 0x80 (Len={len(payload)})...")
        resp, sw = self.send_apdu(self.CMD_CHANGE_FILE_SETTINGS, data=final_apdu)
        print(f"  -> SW={hex(sw)}")

    def probe_variants(self):
        print("\n=== PROBING VARIANTS ===")
        # Payload: Disable SDM (00 E0 00) - 3 bytes
        payload = bytes.fromhex("00 E0 00")
        
        try:
            self.authenticate(0, "00000000000000000000000000000000")
            # Set keys from last auth
            self.key_enc = self.last_k1
            self.key_mac = self.last_k2
        except: return

        # Variant 1: FileNo Plain, Payload Encrypted
        # BUT MAC includes FileNo!
        print("\nTesting Variant 1: FileNo Plain, Payload Encrypted (MAC includes FileNo)...")
        enc_payload = self.encrypt_data(payload) # 3 -> 16 bytes
        
        self.cmd_counter += 1
        
        # MAC over: Cmd + Ctr + TI + FileNo + EncPayload
        msg = bytes([self.CMD_CHANGE_FILE_SETTINGS]) + self.cmd_counter.to_bytes(2, 'little') + self.ti + bytes([0x02]) + enc_payload
        c = CMAC.new(self.key_mac, ciphermod=AES)
        c.update(msg)
        mac = c.digest()[:8]
        
        final_apdu = bytes([0x02]) + enc_payload + mac
        resp, sw = self.send_apdu(self.CMD_CHANGE_FILE_SETTINGS, data=final_apdu)
        print(f"  -> SW={hex(sw)}")
        if sw == 0x9000: 
            print("  ✅ SUCCESS! FileNo MUST be Plain!")
            return

        # Variant 2: Plain + MAC (CommMode.Mac)
        print("\nTesting Variant 2: Plain + MAC...")
        try:
            self.authenticate(0, "00000000000000000000000000000000")
            self.key_enc = self.last_k1
            self.key_mac = self.last_k2
        except: return
        
        # MAC over: Cmd + Ctr + TI + FileNo + Payload
        self.cmd_counter += 1
        # Manual MAC calculation to include FileNo
        msg = bytes([self.CMD_CHANGE_FILE_SETTINGS]) + self.cmd_counter.to_bytes(2, 'little') + self.ti + bytes([0x02]) + payload
        c = CMAC.new(self.key_mac, ciphermod=AES)
        c.update(msg)
        mac = c.digest()[:8]
        
        final_apdu = bytes([0x02]) + payload + mac
        resp, sw = self.send_apdu(self.CMD_CHANGE_FILE_SETTINGS, data=final_apdu)
        print(f"  -> SW={hex(sw)}")
        if sw == 0x9000: print("  ✅ SUCCESS!")

    def probe_get_file_ids(self):
        print("\n=== PROBING GetFileIDs (0x6F) ===")
        try:
            self.authenticate(0, "00000000000000000000000000000000")
            # Assume k1=Enc, k2=Mac
            self.key_enc = self.last_k1
            self.key_mac = self.last_k2
        except: return

        # GetFileIDs: Cmd 0x6F. No data.
        # CommMode.Mac? Or Plain?
        # Usually GetFileIDs is allowed in Plain.
        # But let's try with MAC to verify Session Keys.
        
        self.cmd_counter += 1
        mac = self.calculate_cmac(0x6F, b"")
        
        final_apdu = mac
        
        print(f"Sending GetFileIDs (MAC'd)...")
        resp, sw = self.send_apdu(0x6F, data=final_apdu)
        print(f"  -> SW={hex(sw)}")
        if sw == 0x9000:
            print(f"  ✅ SUCCESS! File IDs: {resp.hex()}")
        else:
            print(f"  ❌ Failed. SW={hex(sw)}")

    def probe_get_file_settings_encrypted(self):
        print("\n=== PROBING GetFileSettings (Encrypted) ===")
        try:
            self.authenticate(0, "00000000000000000000000000000000")
            self.key_enc = self.last_k1
            self.key_mac = self.last_k2
        except: return

        # Try File 1 and File 2
        for file_no in [1, 2]:
            print(f"Checking File {file_no}...")
            data = bytes([file_no])
            enc_data = self.encrypt_data(data)
            
            self.cmd_counter += 1
            mac = self.calculate_cmac(self.CMD_GET_FILE_SETTINGS, enc_data)
            
            final_apdu = enc_data + mac
            
            print(f"  Sending GetFileSettings Encrypted...")
            resp, sw = self.send_apdu(self.CMD_GET_FILE_SETTINGS, data=final_apdu)
            print(f"  -> SW={hex(sw)}")
            if sw == 0x9000:
                print(f"  ✅ SUCCESS! Settings: {resp.hex()}")
            elif sw == 0x917E:
                print(f"  -> Length Error")
            
    def probe_kdf_variants(self):
        print("\n=== PROBING KDF VARIANTS ===")
        # Try Unrotated RndB
        try:
            self.authenticate(0, "00000000000000000000000000000000")
            
            # Re-derive keys with Unrotated RndB
            # We need to call DLL manually here
            dll_name = os.path.abspath('OUR_MIFARE.dll')
            lib = ctypes.cdll.LoadLibrary(dll_name)
            
            # We don't have RndA/RndB here because they are local to authenticate
            # We need to capture them in authenticate.
        except: return

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
        
        # TI is the first 4 bytes of RndB
        self.ti = rnd_b[:4]
        print(f"✓ TI Extracted from RndB: {self.ti.hex().upper()}")
        
        # Part 2
        rnd_a = get_random_bytes(16)
        rnd_b_prime = self.rotate_left(rnd_b)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        token = cipher.encrypt(rnd_a + rnd_b_prime)
        
        resp, sw = self.send_apdu(0xAF, data=token)
        if sw != 0x9000 and sw != 0x9100: raise Exception(f"Auth Part 2 Failed: {hex(sw)}")
        
        # Capture RndA, RndB for probing
        self.last_rnd_a = rnd_a
        self.last_rnd_b = rnd_b
        self.last_key = key
        
        # Generate keys (Standard)
        self._generate_session_keys(rnd_a, rnd_b, key)
        return True

    def probe_kdf_rotation(self):
        print("\n=== PROBING KDF ROTATION ===")
        
        # 1. Rotated (Standard - already set by authenticate)
        print("Testing Rotated RndB (Standard)...")
        try:
            self.authenticate(0, "00000000000000000000000000000000")
        except: return

        # Payload: Disable SDM
        payload = bytes.fromhex("00 E0 00")
        full_data = bytes([0x02]) + payload
        enc_data = self.encrypt_data(full_data)
        self.cmd_counter += 1
        mac = self.calculate_cmac(self.CMD_CHANGE_FILE_SETTINGS, enc_data)
        resp, sw = self.send_apdu(self.CMD_CHANGE_FILE_SETTINGS, data=enc_data + mac, le=None)
        print(f"  -> SW={hex(sw)}")
        if sw == 0x9000: 
            print("  ✅ SUCCESS with Rotated RndB!")
            return

        # 2. Unrotated RndB
        print("Testing Unrotated RndB...")
        
        # Call DLL with Unrotated
        dll_name = os.path.abspath('OUR_MIFARE.dll')
        lib = ctypes.cdll.LoadLibrary(dll_name)
        
        rnd_a = self.last_rnd_a
        rnd_b = self.last_rnd_b # Unrotated
        key = self.last_key
        
        randdata = (ctypes.c_ubyte * 32)(*list(rnd_a + rnd_b))
        key_buf = (ctypes.c_ubyte * 16)(*list(key))
        result_buf = (ctypes.c_ubyte * 32)()
        lib.cpucalcexauthkey(ctypes.byref(randdata), ctypes.byref(key_buf), 16, ctypes.byref(result_buf))
        res_bytes = bytes(result_buf)
        
        k1 = res_bytes[:16]
        k2 = res_bytes[16:]
        
        # Try k1=Enc, k2=Mac
        self.key_enc = k1
        self.key_mac = k2
        
        # Authenticate again to reset counter? 
        # No, just try.
        # But wait, if previous command failed, counter might be sync?
        # Let's restart auth to be safe.
        try:
            self.authenticate(0, "00000000000000000000000000000000")
        except: return
        
        # Re-derive Unrotated Keys (because Auth generated Rotated ones)
        rnd_a = self.last_rnd_a
        rnd_b = self.last_rnd_b
        randdata = (ctypes.c_ubyte * 32)(*list(rnd_a + rnd_b))
        lib.cpucalcexauthkey(ctypes.byref(randdata), ctypes.byref(key_buf), 16, ctypes.byref(result_buf))
        res_bytes = bytes(result_buf)
        self.key_enc = res_bytes[:16]
        self.key_mac = res_bytes[16:]
        
        self.cmd_counter += 1
        full_data = bytes([0x02]) + payload
        enc_data = self.encrypt_data(full_data)
        mac = self.calculate_cmac(self.CMD_CHANGE_FILE_SETTINGS, enc_data)
        resp, sw = self.send_apdu(self.CMD_CHANGE_FILE_SETTINGS, data=enc_data + mac, le=None)
        print(f"  -> SW={hex(sw)}")
        if sw == 0x9000: 
            print("  ✅ SUCCESS with Unrotated RndB!")

    def probe_comm_mode_mac(self):
        print("\n=== PROBING CommMode.Mac ===")
        try:
            self.authenticate(0, "00000000000000000000000000000000")
            # Use Standard Keys (Rotated)
            self.key_enc = self.last_k1
            self.key_mac = self.last_k2
        except: return

        payload = bytes.fromhex("00 E0 00")
        
        self.cmd_counter += 1
        # MAC over: Cmd + Ctr + TI + FileNo + Payload
        msg = bytes([self.CMD_CHANGE_FILE_SETTINGS]) + self.cmd_counter.to_bytes(2, 'little') + self.ti + bytes([0x02]) + payload
        c = CMAC.new(self.key_mac, ciphermod=AES)
        c.update(msg)
        mac = c.digest()[:8]
        
        final_apdu = bytes([0x02]) + payload + mac
        
        print(f"Sending ChangeFileSettings (MAC, No Le, Len={len(final_apdu)})...")
        resp, sw = self.send_apdu(self.CMD_CHANGE_FILE_SETTINGS, data=final_apdu, le=None)
        print(f"  -> SW={hex(sw)}")
        if sw == 0x9000: 
            print("  ✅ SUCCESS with CommMode.Mac!")

    def probe_get_file_settings_encrypted_no_le(self):
        print("\n=== PROBING GetFileSettings (Encrypted, No Le) ===")
        try:
            self.authenticate(0, "00000000000000000000000000000000")
            self.key_enc = self.last_k1
            self.key_mac = self.last_k2
        except: return

        # GetFileSettings: F5 [FileNo]
        data = bytes([0x02])
        enc_data = self.encrypt_data(data)
        
        self.cmd_counter += 1
        mac = self.calculate_cmac(self.CMD_GET_FILE_SETTINGS, enc_data)
        
        final_apdu = enc_data + mac
        
        print(f"Sending GetFileSettings Encrypted (Len={len(final_apdu)})...")
        resp, sw = self.send_apdu(self.CMD_GET_FILE_SETTINGS, data=final_apdu, le=None)
        print(f"  -> SW={hex(sw)}")
        if sw == 0x9000:
            print(f"  ✅ SUCCESS! Settings: {resp.hex()}")
        elif sw == 0x917E:
            print(f"  -> Length Error")

    def probe_get_file_settings_mac_unrotated(self):
        print("\n=== PROBING GetFileSettings (MAC, Unrotated) ===")
        try:
            self.authenticate(0, "00000000000000000000000000000000")
        except: return

        # Re-derive Unrotated Keys
        dll_name = os.path.abspath('OUR_MIFARE.dll')
        lib = ctypes.cdll.LoadLibrary(dll_name)
        
        rnd_a = self.last_rnd_a
        rnd_b = self.last_rnd_b # Unrotated
        key = self.last_key
        
        randdata = (ctypes.c_ubyte * 32)(*list(rnd_a + rnd_b))
        key_buf = (ctypes.c_ubyte * 16)(*list(key))
        result_buf = (ctypes.c_ubyte * 32)()
        lib.cpucalcexauthkey(ctypes.byref(randdata), ctypes.byref(key_buf), 16, ctypes.byref(result_buf))
        res_bytes = bytes(result_buf)
        
        # Try Standard: k1=Enc, k2=Mac
        self.key_enc = res_bytes[:16]
        self.key_mac = res_bytes[16:]
        
        # GetFileSettings: F5 [FileNo] [MAC]
        data = bytes([0x02])
        self.cmd_counter += 1
        msg = bytes([self.CMD_GET_FILE_SETTINGS]) + self.cmd_counter.to_bytes(2, 'little') + self.ti + data
        c = CMAC.new(self.key_mac, ciphermod=AES)
        c.update(msg)
        mac = c.digest()[:8]
        
        final_apdu = data + mac
        
        print(f"Sending GetFileSettings MAC (Unrotated) (Len={len(final_apdu)})...")
        # Use Le=00
        resp, sw = self.send_apdu(self.CMD_GET_FILE_SETTINGS, data=final_apdu)
        print(f"  -> SW={hex(sw)}")
        if sw == 0x9000:
            print(f"  ✅ SUCCESS! Settings: {resp.hex()}")
            return
            
        # Try Swapped: k1=Mac
        self.key_enc = res_bytes[16:]
        self.key_mac = res_bytes[:16]
        
        c = CMAC.new(self.key_mac, ciphermod=AES)
        c.update(msg) # Reuse msg? No, same msg.
        mac = c.digest()[:8]
        final_apdu = data + mac
        print(f"Sending GetFileSettings MAC (Unrotated, Swapped)...")
        # Use Le=00
        resp, sw = self.send_apdu(self.CMD_GET_FILE_SETTINGS, data=final_apdu)
        print(f"  -> SW={hex(sw)}")
        if sw == 0x9000:
            print(f"  ✅ SUCCESS! Settings: {resp.hex()}")

    def probe_len6_swapped(self):
        print("\n=== PROBING LEN 6 SWAPPED (Enc=k2) ===")
        # Payload: Len 6
        payload = bytes.fromhex("40 E0 00 81 EE 0E")
        
        try:
            self.authenticate(0, "00000000000000000000000000000000")
            # Enc=k2, Mac=k1 (Try this combo)
            self.key_enc = self.last_k2
            self.key_mac = self.last_k1
        except: return

        full_data = bytes([0x02]) + payload
        enc_data = self.encrypt_data(full_data)
        
        self.cmd_counter += 1
        mac = self.calculate_cmac(self.CMD_CHANGE_FILE_SETTINGS, enc_data)
        
        final_apdu = enc_data + mac
        
        print(f"Sending Len 6 Swapped (Enc=k2)...")
        # Use Le=00 (Default) since No Le caused 917E
        resp, sw = self.send_apdu(self.CMD_CHANGE_FILE_SETTINGS, data=final_apdu)
        print(f"  -> SW={hex(sw)}")
        if sw == 0x91F0:
            print("  -> File Not Found (Enc Wrong)")
        elif sw == 0x919E:
            print("  -> Value Error (Enc Likely Correct!)")

    def probe_len9_swapped(self):
        print("\n=== PROBING LEN 9 SWAPPED (Enc=k2) ===")
        # Payload: Len 9 (UID Offset)
        # SDMOpt=0x81 (UID+ASCII) requires UIDOffset
        payload = bytes.fromhex("40 E0 00 81 EE 0E") + bytes.fromhex("00 00 00")
        
        try:
            self.authenticate(0, "00000000000000000000000000000000")
            # Enc=k2, Mac=k1
            self.key_enc = self.last_k2
            self.key_mac = self.last_k1
        except: return

        full_data = bytes([0x02]) + payload
        enc_data = self.encrypt_data(full_data)
        
        self.cmd_counter += 1
        mac = self.calculate_cmac(self.CMD_CHANGE_FILE_SETTINGS, enc_data)
        
        final_apdu = enc_data + mac
        
        print(f"Sending Len 9 Swapped (Enc=k2)...")
        resp, sw = self.send_apdu(self.CMD_CHANGE_FILE_SETTINGS, data=final_apdu)
        print(f"  -> SW={hex(sw)}")
        if sw == 0x9000:
            print("  ✅ SUCCESS!")

    def probe_len3_swapped(self):
        print("\n=== PROBING LEN 3 SWAPPED (Enc=k2) ===")
        # Payload: Len 3 (Disable SDM)
        payload = bytes.fromhex("00 E0 00")
        
        try:
            self.authenticate(0, "00000000000000000000000000000000")
            # Enc=k2, Mac=k1
            self.key_enc = self.last_k2
            self.key_mac = self.last_k1
        except: return

        full_data = bytes([0x02]) + payload
        enc_data = self.encrypt_data(full_data)
        
        self.cmd_counter += 1
        mac = self.calculate_cmac(self.CMD_CHANGE_FILE_SETTINGS, enc_data)
        
        final_apdu = enc_data + mac
        
        print(f"Sending Len 3 Swapped (Enc=k2)...")
        resp, sw = self.send_apdu(self.CMD_CHANGE_FILE_SETTINGS, data=final_apdu)
        print(f"  -> SW={hex(sw)}")
        if sw == 0x9000:
            print("  ✅ SUCCESS!")

    def probe_valid_sdm(self):
        print("\n=== PROBING VALID SDM (Enc=k2, Mac=k1) ===")
        try:
            self.authenticate(0, "00000000000000000000000000000000")
            # Enc=k2, Mac=k1 (Standard)
            self.key_enc = self.last_k2
            self.key_mac = self.last_k1
        except: return

        # Payload: FileOpt(40) + AR(E0 00) + SDMOpt(80) + SDMAR(EE 0E) + UIDOff(32)
        # Len 9
        payload = bytes.fromhex("40 E0 00 80 EE 0E") + struct.pack("<I", 32)[:3]
        
        full_data = bytes([0x02]) + payload
        enc_data = self.encrypt_data(full_data)
        
        self.cmd_counter += 1
        mac = self.calculate_cmac(self.CMD_CHANGE_FILE_SETTINGS, enc_data)
        
        final_apdu = enc_data + mac
        
        print(f"Sending Valid SDM 0x80 (Enc=k2, Mac=k1)...")
        # Use Le=00
        resp, sw = self.send_apdu(self.CMD_CHANGE_FILE_SETTINGS, data=final_apdu)
        print(f"  -> SW={hex(sw)}")
        if sw == 0x9000:
            print("  ✅ SUCCESS!")

    def probe_hybrid_keys(self):
        print("\n=== PROBING HYBRID (Enc=k0, Mac=k1) ===")
        try:
            self.authenticate(0, "00000000000000000000000000000000")
            # Enc=Key0, Mac=k1
            self.key_enc = bytes.fromhex("00000000000000000000000000000000")
            self.key_mac = self.last_k1
        except: return

        # Payload: Valid SDM (Len 9)
        payload = bytes.fromhex("40 E0 00 80 EE 0E") + struct.pack("<I", 32)[:3]
        
        full_data = bytes([0x02]) + payload
        enc_data = self.encrypt_data(full_data)
        
        self.cmd_counter += 1
        mac = self.calculate_cmac(self.CMD_CHANGE_FILE_SETTINGS, enc_data)
        
        final_apdu = enc_data + mac
        
        print(f"Sending Hybrid (Enc=k0, Mac=k1)...")
        resp, sw = self.send_apdu(self.CMD_CHANGE_FILE_SETTINGS, data=final_apdu)
        print(f"  -> SW={hex(sw)}")
        if sw == 0x9000:
            print("  ✅ SUCCESS!")

    def probe_delete_file(self):
        print("\n=== PROBING DELETE FILE (Enc=k1, Mac=k2) ===")
        try:
            self.authenticate(0, "00000000000000000000000000000000")
            # Enc=k1, Mac=k2
            self.key_enc = self.last_k1
            self.key_mac = self.last_k2
        except: return

        # DeleteFile: DF [FileNo]
        data = bytes([0x02])
        enc_data = self.encrypt_data(data)
        
        self.cmd_counter += 1
        mac = self.calculate_cmac(0xDF, enc_data)
        
        final_apdu = enc_data + mac
        
        print(f"Sending DeleteFile(2)...")
        resp, sw = self.send_apdu(0xDF, data=final_apdu)
        print(f"  -> SW={hex(sw)}")
        if sw == 0x9000:
            print("  ✅ SUCCESS! File Deleted.")

    def probe_delete_file_mac(self):
        print("\n=== PROBING DELETE FILE MAC (Enc=k1, Mac=k2) ===")
        try:
            self.authenticate(0, "00000000000000000000000000000000")
            self.key_enc = self.last_k1
            self.key_mac = self.last_k2
        except: return

        # DeleteFile: DF [FileNo]
        data = bytes([0x02])
        
        self.cmd_counter += 1
        msg = bytes([0xDF]) + self.cmd_counter.to_bytes(2, 'little') + self.ti + data
        c = CMAC.new(self.key_mac, ciphermod=AES)
        c.update(msg)
        mac = c.digest()[:8]
        
        final_apdu = data + mac
        
        print(f"Sending DeleteFile(2) MAC...")
        resp, sw = self.send_apdu(0xDF, data=final_apdu)
        print(f"  -> SW={hex(sw)}")
        if sw == 0x9000:
            print("  ✅ SUCCESS! File Deleted.")

    def probe_p1_fileno(self):
        print("\n=== PROBING P1=FileNo ===")
        try:
            self.authenticate(0, "00000000000000000000000000000000")
            # Enc=k1, Mac=k2 (Assume this for now)
            self.key_enc = self.last_k1
            self.key_mac = self.last_k2
        except: return

        # Payload: 00 E0 00
        payload = bytes.fromhex("00 E0 00")
        enc_payload = self.encrypt_data(payload) # Pad to 16
        
        self.cmd_counter += 1
        # MAC over: Cmd + Ctr + TI + Header(P1=02) + EncData?
        # If P1 is FileNo, is it in header or data for MAC?
        # Usually header.
        # But wait, standard EV2 MAC covers `Cmd + Ctr + TI + Data`.
        # `Data` starts with `FileNo` if FileNo is in data.
        # If FileNo is in P1, it's not in data.
        
        msg = bytes([self.CMD_CHANGE_FILE_SETTINGS]) + self.cmd_counter.to_bytes(2, 'little') + self.ti + enc_payload
        c = CMAC.new(self.key_mac, ciphermod=AES)
        c.update(msg)
        mac = c.digest()[:8]
        
        final_apdu = enc_payload + mac
        
        # Manually send with P1=02
        header = [0x90, self.CMD_CHANGE_FILE_SETTINGS, 0x02, 0x00]
        apdu = header + [len(final_apdu)] + list(final_apdu)
        # No Le
        
        print(f"Sending ChangeFileSettings (P1=02)...")
        resp, sw1, sw2 = self.connection.transmit(apdu)
        sw = (sw1 << 8 | sw2)
        print(f"  -> SW={hex(sw)}")
        if sw == 0x9000:
            print("  ✅ SUCCESS!")

    def probe_valid_sdm_k1(self):
        print("\n=== PROBING VALID SDM VARIANTS (Enc=k1, Mac=k2) ===")
        try:
            self.authenticate(0, "00000000000000000000000000000000")
            self.key_enc = self.last_k1
            self.key_mac = self.last_k2
        except: return

        # Try various payloads
        # Format: (Name, PayloadBytes)
        variants = [
            ("Std SDM (Off=32)", bytes.fromhex("40 E0 00 80 EE 0E 20 00 00")),
            ("Std SDM (Off=0)", bytes.fromhex("40 E0 00 80 EE 0E 00 00 00")),
            ("CommMode.Mac (41)", bytes.fromhex("41 E0 00 80 EE 0E 20 00 00")),
            ("CommMode.Enc (43)", bytes.fromhex("43 E0 00 80 EE 0E 20 00 00")),
            ("AR=0000", bytes.fromhex("40 00 00 80 EE 0E 20 00 00")),
            ("AR=F000", bytes.fromhex("40 F0 00 80 EE 0E 20 00 00")),
            ("AR=00E0", bytes.fromhex("40 00 E0 80 EE 0E 20 00 00")),
            ("SDMAR=FFFF", bytes.fromhex("40 E0 00 80 FF FF 20 00 00")),
        ]
        
        for name, payload in variants:
            print(f"Testing {name}...")
            # Re-auth? No, chained commands OK if no error. 
            # But 919E might abort session?
            # Let's re-auth to be safe.
            try:
                self.authenticate(0, "00000000000000000000000000000000")
                self.key_enc = self.last_k1
                self.key_mac = self.last_k2
            except: continue

            full_data = bytes([0x02]) + payload
            enc_data = self.encrypt_data(full_data)
            
            self.cmd_counter += 1
            mac = self.calculate_cmac(self.CMD_CHANGE_FILE_SETTINGS, enc_data)
            
            final_apdu = enc_data + mac
            
            resp, sw = self.send_apdu(self.CMD_CHANGE_FILE_SETTINGS, data=final_apdu)
            print(f"  -> SW={hex(sw)}")
            if sw == 0x9000:
                print("  ✅ SUCCESS!")
                return

    def probe_delete_file_k2(self):
        print("\n=== PROBING DELETE FILE (Enc=k2, Mac=k1) ===")
        try:
            self.authenticate(0, "00000000000000000000000000000000")
            # Enc=k2, Mac=k1
            self.key_enc = self.last_k2
            self.key_mac = self.last_k1
        except: return

        # DeleteFile: DF [FileNo]
        data = bytes([0x02])
        enc_data = self.encrypt_data(data)
        
        self.cmd_counter += 1
        mac = self.calculate_cmac(0xDF, enc_data)
        
        final_apdu = enc_data + mac
        
        print(f"Sending DeleteFile(2) (Enc=k2)...")
        # Use Le=00
        resp, sw = self.send_apdu(0xDF, data=final_apdu)
        print(f"  -> SW={hex(sw)}")
        if sw == 0x9000:
            print("  ✅ SUCCESS! File Deleted.")

    def probe_delete_file_plain(self):
        print("\n=== PROBING DELETE FILE (Plain) ===")
        try:
            self.authenticate(0, "00000000000000000000000000000000")
        except: return

        # DeleteFile: DF [FileNo]
        final_apdu = bytes([0x02])
        
        print(f"Sending DeleteFile(2) (Plain)...")
        resp, sw = self.send_apdu(0xDF, data=final_apdu)
        print(f"  -> SW={hex(sw)}")
        if sw == 0x9000:
            print("  ✅ SUCCESS! File Deleted.")

    def probe_k2_variants(self):
        print("\n=== PROBING K2 VARIANTS (Enc=k2, Mac=k1) ===")
        try:
            self.authenticate(0, "00000000000000000000000000000000")
            # Enc=k2, Mac=k1
            self.key_enc = self.last_k2
            self.key_mac = self.last_k1
        except: return

        # Format: (Name, PayloadBytes)
        variants = [
            ("Disable SDM (00 E0 00)", bytes.fromhex("00 E0 00")),
            ("Disable SDM (00 00 00)", bytes.fromhex("00 00 00")),
            ("Disable SDM (00 F0 00)", bytes.fromhex("00 F0 00")),
            ("Enable SDM (40 E0 00)", bytes.fromhex("40 E0 00")), # Invalid len? No, len 3 implies no params? Or just enable?
            # If 40 (SDM) is set, params MUST follow?
            # Yes, if Bit 6 is set, SDM Params follow.
            # If I send 3 bytes, params missing -> 0x919E or 0x917E?
            # 0x919E (Parameter Error).
            
            # So try VALID SDM payloads with k2
            ("Valid SDM (40 E0 00 80 EE 0E 20 00 00)", bytes.fromhex("40 E0 00 80 EE 0E 20 00 00")),
            ("Valid SDM (AR=0000)", bytes.fromhex("40 00 00 80 EE 0E 20 00 00")),
        ]
        
        for name, payload in variants:
            print(f"Testing {name}...")
            # Re-auth?
            try:
                self.authenticate(0, "00000000000000000000000000000000")
                self.key_enc = self.last_k2
                self.key_mac = self.last_k1
            except: continue

            full_data = bytes([0x02]) + payload
            enc_data = self.encrypt_data(full_data)
            
            self.cmd_counter += 1
            mac = self.calculate_cmac(self.CMD_CHANGE_FILE_SETTINGS, enc_data)
            
            final_apdu = enc_data + mac
            
            resp, sw = self.send_apdu(self.CMD_CHANGE_FILE_SETTINGS, data=final_apdu)
            print(f"  -> SW={hex(sw)}")
            if sw == 0x9000:
                print("  ✅ SUCCESS!")
                return

    def probe_fileno_plain_len25(self):
        print("\n=== PROBING FileNo PLAIN (Len 25) ===")
        try:
            self.authenticate(0, "00000000000000000000000000000000")
            # Enc=k1, Mac=k2 (Best guess for now)
            self.key_enc = self.last_k1
            self.key_mac = self.last_k2
        except: return

        # Payload: 00 E0 00
        payload = bytes.fromhex("00 E0 00")
        enc_payload = self.encrypt_data(payload)
        
        self.cmd_counter += 1
        # MAC over: Cmd + Ctr + TI + Header(02) + EncData
        msg = bytes([self.CMD_CHANGE_FILE_SETTINGS]) + self.cmd_counter.to_bytes(2, 'little') + self.ti + bytes([0x02]) + enc_payload
        c = CMAC.new(self.key_mac, ciphermod=AES)
        c.update(msg)
        mac = c.digest()[:8]
        
        final_apdu = bytes([0x02]) + enc_payload + mac
        
        print(f"Sending Len 25 (FileNo Plain)...")
        # Use No Le
        resp, sw = self.send_apdu(self.CMD_CHANGE_FILE_SETTINGS, data=final_apdu, le=None)
        print(f"  -> SW={hex(sw)}")
        if sw == 0x9000:
            print("  ✅ SUCCESS!")

    def probe_delete_file_no_le(self):
        print("\n=== PROBING DELETE FILE (Enc=k1, Mac=k2, No Le) ===")
        try:
            self.authenticate(0, "00000000000000000000000000000000")
            self.key_enc = self.last_k1
            self.key_mac = self.last_k2
        except: return

        data = bytes([0x02])
        enc_data = self.encrypt_data(data)
        
        self.cmd_counter += 1
        mac = self.calculate_cmac(0xDF, enc_data)
        
        final_apdu = enc_data + mac
        
        print(f"Sending DeleteFile(2)...")
        resp, sw = self.send_apdu(0xDF, data=final_apdu, le=None)
        print(f"  -> SW={hex(sw)}")
        if sw == 0x9000:
            print("  ✅ SUCCESS! File Deleted.")

    def probe_payloads_k1(self):
        print("\n=== PROBING PAYLOADS (Enc=k1, Mac=k2) ===")
        try:
            self.authenticate(0, "00000000000000000000000000000000")
            # Enc=k1, Mac=k2
            self.key_enc = self.last_k1
            self.key_mac = self.last_k2
        except: return

        # Offsets
        uid_off = bytes.fromhex("20 00 00")
        mac_off = bytes.fromhex("40 00 00")
        
        # Format: (Name, PayloadBytes)
        variants = [
            # 1. Disable SDM (Most Basic)
            ("Disable SDM (00 E0 00)", bytes.fromhex("00 E0 00")),
            
            # 2. SDM 0x80 (UID Only)
            ("SDM 0x80 (Len 9)", bytes.fromhex("40 E0 00 80 EE 0E") + uid_off),
            
            # 3. SDM 0x81 (UID + MAC) - Len 12
            ("SDM 0x81 (Len 12)", bytes.fromhex("40 E0 00 81 EE 0E") + uid_off + mac_off),
            
            # 4. SDM 0x80 with Dummy MAC Offset (Len 12) - In case fixed length expected
            ("SDM 0x80 (Len 12 - Dummy)", bytes.fromhex("40 E0 00 80 EE 0E") + uid_off + bytes.fromhex("00 00 00")),
            
            # 5. SDM 0x81 with 3 Offsets (Len 15)
            ("SDM 0x81 (Len 15 - 3 Offsets)", bytes.fromhex("40 E0 00 81 EE 0E") + uid_off + mac_off + mac_off),
            
            # 6. Try AR=00 00 (Key 0)
            ("Disable SDM (AR=0000)", bytes.fromhex("00 00 00")),
            ("SDM 0x80 (AR=0000)", bytes.fromhex("40 00 00 80 EE 0E") + uid_off),
            
            # 7. Try SDMAR=FF FF
            ("SDM 0x80 (SDMAR=FFFF)", bytes.fromhex("40 E0 00 80 FF FF") + uid_off),
        ]
        
        for name, payload in variants:
            print(f"Testing {name}...")
            # Re-auth for safety
            try:
                self.authenticate(0, "00000000000000000000000000000000")
                self.key_enc = self.last_k1
                self.key_mac = self.last_k2
            except: continue

            full_data = bytes([0x02]) + payload
            enc_data = self.encrypt_data(full_data)
            
            self.cmd_counter += 1
            mac = self.calculate_cmac(self.CMD_CHANGE_FILE_SETTINGS, enc_data)
            
            final_apdu = enc_data + mac
            
            resp, sw = self.send_apdu(self.CMD_CHANGE_FILE_SETTINGS, data=final_apdu)
            print(f"  -> SW={hex(sw)}")
            if sw == 0x9000:
                print("  ✅ SUCCESS!")
                return

    def probe_get_settings_formats(self):
        print("\n=== PROBING GetFileSettings FORMATS (Enc=k1, Mac=k2) ===")
        try:
            self.authenticate(0, "00000000000000000000000000000000")
            self.key_enc = self.last_k1
            self.key_mac = self.last_k2
        except: return

        # 1. Plain (1 byte)
        print("Testing Plain (1 byte)...")
        resp, sw = self.send_apdu(self.CMD_GET_FILE_SETTINGS, data=bytes([0x02]))
        print(f"  -> SW={hex(sw)}")
        if sw == 0x9000:
            print(f"  ✅ SUCCESS! Resp: {resp.hex()}")
            return

        # 2. MAC (9 bytes)
        print("Testing MAC (9 bytes)...")
        data = bytes([0x02])
        self.cmd_counter += 1
        msg = bytes([self.CMD_GET_FILE_SETTINGS]) + self.cmd_counter.to_bytes(2, 'little') + self.ti + data
        c = CMAC.new(self.key_mac, ciphermod=AES)
        c.update(msg)
        mac = c.digest()[:8]
        resp, sw = self.send_apdu(self.CMD_GET_FILE_SETTINGS, data=data + mac)
        print(f"  -> SW={hex(sw)}")
        if sw == 0x9000:
            print(f"  ✅ SUCCESS! Resp: {resp.hex()}")
            return

        # 3. Encrypted (24 bytes)
        print("Testing Encrypted (24 bytes)...")
        data = bytes([0x02])
        enc_data = self.encrypt_data(data) # 16 bytes
        self.cmd_counter += 1 # Increment for new command
        mac = self.calculate_cmac(self.CMD_GET_FILE_SETTINGS, enc_data) # 8 bytes
        resp, sw = self.send_apdu(self.CMD_GET_FILE_SETTINGS, data=enc_data + mac)
        print(f"  -> SW={hex(sw)}")
        if sw == 0x9000:
            print(f"  ✅ SUCCESS! Resp: {resp.hex()}")
            return

    def probe_deep_diagnostics(self):
        print("\n=== DEEP DIAGNOSTICS (Enc=k1, Mac=k2) ===")
        try:
            self.authenticate(0, "00000000000000000000000000000000")
            self.key_enc = self.last_k1
            self.key_mac = self.last_k2
        except: return

        # 1. GetCardUID (0x51)
        # Expectation: Encrypted RndA' + MAC? No, just Data + MAC?
        # GetCardUID is 0x51. EV2: Cmd + MAC.
        # Response: Enc(UID) + MAC.
        print("\n1. Testing GetCardUID (0x51)...")
        self.cmd_counter += 1
        msg = bytes([0x51]) + self.cmd_counter.to_bytes(2, 'little') + self.ti
        c = CMAC.new(self.key_mac, ciphermod=AES)
        c.update(msg)
        mac = c.digest()[:8]
        resp, sw = self.send_apdu(0x51, data=mac)
        print(f"  -> SW={hex(sw)}")
        if sw == 0x9000:
            print(f"  ✅ SUCCESS! UID Data: {resp.hex()}")
        
        # 2. GetFileSettings (0xF5) - Retry Plain+MAC
        # Maybe FileNo needs to be padded in Plain mode? No.
        print("\n2. Testing GetFileSettings(2) (Plain+MAC)...")
        data = bytes([0x02])
        self.cmd_counter += 1
        msg = bytes([0xF5]) + self.cmd_counter.to_bytes(2, 'little') + self.ti + data
        c = CMAC.new(self.key_mac, ciphermod=AES)
        c.update(msg)
        mac = c.digest()[:8]
        resp, sw = self.send_apdu(0xF5, data=data + mac)
        print(f"  -> SW={hex(sw)}")
        
        # 3. ChangeFileSettings(2) - Try 00 00 00 (Key 0)
        print("\n3. Testing ChangeFileSettings(2) (00 00 00)...")
        payload = bytes.fromhex("00 00 00")
        full_data = bytes([0x02]) + payload
        enc_data = self.encrypt_data(full_data)
        self.cmd_counter += 1
        mac = self.calculate_cmac(self.CMD_CHANGE_FILE_SETTINGS, enc_data)
        resp, sw = self.send_apdu(self.CMD_CHANGE_FILE_SETTINGS, data=enc_data + mac)
        print(f"  -> SW={hex(sw)}")
        
        # 4. ChangeFileSettings(1) - Try 00 00 00
        print("\n4. Testing ChangeFileSettings(1) (00 00 00)...")
        payload = bytes.fromhex("00 00 00")
        full_data = bytes([0x01]) + payload
        enc_data = self.encrypt_data(full_data)
        self.cmd_counter += 1
        mac = self.calculate_cmac(self.CMD_CHANGE_FILE_SETTINGS, enc_data)
        resp, sw = self.send_apdu(self.CMD_CHANGE_FILE_SETTINGS, data=enc_data + mac)
        print(f"  -> SW={hex(sw)}")

    def encrypt_data_zero_padding(self, data, key=None):
        if key is None:
            key = self.key_enc
        # Zero Padding
        padded_data = bytearray(data)
        while len(padded_data) % 16 != 0:
            padded_data.append(0x00)
        
        iv = bytes(16)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        return cipher.encrypt(bytes(padded_data))

    def probe_zero_padding(self):
        print("\n=== PROBING ZERO PADDING (Enc=k1, Mac=k2) ===")
        try:
            self.authenticate(0, "00000000000000000000000000000000")
            self.key_enc = self.last_k1
            self.key_mac = self.last_k2
        except: return

        # Payload: Disable SDM (00 E0 00)
        payload = bytes.fromhex("00 E0 00")
        full_data = bytes([0x02]) + payload
        
        # Use Zero Padding
        enc_data = self.encrypt_data_zero_padding(full_data)
        
        self.cmd_counter += 1
        mac = self.calculate_cmac(self.CMD_CHANGE_FILE_SETTINGS, enc_data)
        
        final_apdu = enc_data + mac
        
        print(f"Sending Disable SDM (Zero Padding)...")
        resp, sw = self.send_apdu(self.CMD_CHANGE_FILE_SETTINGS, data=final_apdu)
        print(f"  -> SW={hex(sw)}")
        if sw == 0x9000:
            print("  ✅ SUCCESS!")

    def probe_get_version(self):
        print("\n=== PROBING GetVersion (0x60) (Enc=k1, Mac=k2) ===")
        try:
            self.authenticate(0, "00000000000000000000000000000000")
            self.key_enc = self.last_k1
            self.key_mac = self.last_k2
        except: return

        # GetVersion: 60 [MAC]
        self.cmd_counter += 1
        msg = bytes([0x60]) + self.cmd_counter.to_bytes(2, 'little') + self.ti
        c = CMAC.new(self.key_mac, ciphermod=AES)
        c.update(msg)
        mac = c.digest()[:8]
        
        resp, sw = self.send_apdu(0x60, data=mac)
        print(f"  -> SW={hex(sw)}")
        if sw == 0x9000:
            print(f"  ✅ SUCCESS! Version Data: {resp.hex()}")
        else:
            print(f"  ❌ Failed. SW={hex(sw)}")

    def probe_get_version_swapped(self):
        print("\n=== PROBING GetVersion SWAPPED (Enc=k2, Mac=k1) ===")
        try:
            self.authenticate(0, "00000000000000000000000000000000")
            # Enc=k2, Mac=k1
            self.key_enc = self.last_k2
            self.key_mac = self.last_k1
        except: return

        # GetVersion: 60 [MAC]
        self.cmd_counter += 1
        msg = bytes([0x60]) + self.cmd_counter.to_bytes(2, 'little') + self.ti
        c = CMAC.new(self.key_mac, ciphermod=AES)
        c.update(msg)
        mac = c.digest()[:8]
        
        resp, sw = self.send_apdu(0x60, data=mac)
        print(f"  -> SW={hex(sw)}")
        if sw == 0x9000:
            print(f"  ✅ SUCCESS! Version Data: {resp.hex()}")
        else:
            print(f"  ❌ Failed. SW={hex(sw)}")

    def xor_bytes(self, a, b):
        return bytes(x ^ y for x, y in zip(a, b))

    def derive_session_keys_python(self, rnd_a, rnd_b, master_key):
        print("Deriving Session Keys (Python)...")
        # EV2 KDF (Based on libfreefare)
        # SV1 = A5 5A 00 01 00 80
        # SV2 = 5A A5 00 01 00 80
        # Data = SV + RndA[0:2] + (RndA ^ RndB)[0:6]
        
        sv1 = bytes.fromhex("A5 5A 00 01 00 80")
        sv2 = bytes.fromhex("5A A5 00 01 00 80")
        
        xor_rnd = self.xor_bytes(rnd_a, rnd_b)
        
        # Suffix = RndA[0:2] + (RndA ^ RndB)[0:6]
        suffix = rnd_a[:2] + xor_rnd[:6]
        
        data_enc = sv1 + suffix
        data_mac = sv2 + suffix
        
        # CMAC
        c_enc = CMAC.new(master_key, ciphermod=AES)
        c_enc.update(data_enc)
        ses_enc = c_enc.digest()
        
        c_mac = CMAC.new(master_key, ciphermod=AES)
        c_mac.update(data_mac)
        ses_mac = c_mac.digest()
        
        print(f"  Python Enc: {ses_enc.hex()}")
        print(f"  Python Mac: {ses_mac.hex()}")
        
        return ses_enc, ses_mac

    def probe_python_kdf(self):
        print("\n=== PROBING PYTHON KDF (GetVersion) ===")
        try:
            self.authenticate(0, "00000000000000000000000000000000")
            
            # Use Python KDF
            self.key_enc, self.key_mac = self.derive_session_keys_python(
                self.last_rnd_a, self.last_rnd_b, self.last_key
            )
        except: return

        # GetVersion: 60 [MAC]
        self.cmd_counter += 1
        msg = bytes([0x60]) + self.cmd_counter.to_bytes(2, 'little') + self.ti
        c = CMAC.new(self.key_mac, ciphermod=AES)
        c.update(msg)
        mac = c.digest()[:8]
        
        resp, sw = self.send_apdu(0x60, data=mac)
        print(f"  -> SW={hex(sw)}")
        if sw == 0x9000:
            print(f"  ✅ SUCCESS! Version Data: {resp.hex()}")
        else:
            print(f"  ❌ Failed. SW={hex(sw)}")

    def probe_no_le_variants(self):
        print("\n=== PROBING NO LE VARIANTS ===")
        
        # 1. Enc=k1, Mac=k2 (Current Best Guess)
        print("\nTesting Enc=k1, Mac=k2 (No Le)...")
        try:
            self.authenticate(0, "00000000000000000000000000000000")
            self.key_enc = self.last_k1
            self.key_mac = self.last_k2
            
            payload = bytes.fromhex("00 E0 00")
            full_data = bytes([0x02]) + payload
            enc_data = self.encrypt_data(full_data)
            self.cmd_counter += 1
            mac = self.calculate_cmac(self.CMD_CHANGE_FILE_SETTINGS, enc_data)
            final_apdu = enc_data + mac
            
            resp, sw = self.send_apdu(self.CMD_CHANGE_FILE_SETTINGS, data=final_apdu, le=None)
            print(f"  -> SW={hex(sw)}")
            if sw == 0x9000: print("  ✅ SUCCESS!")
        except: pass

        # 2. Enc=k2, Mac=k1 (Swapped)
        print("\nTesting Enc=k2, Mac=k1 (No Le)...")
        try:
            self.authenticate(0, "00000000000000000000000000000000")
            self.key_enc = self.last_k2
            self.key_mac = self.last_k1
            
            payload = bytes.fromhex("00 E0 00")
            full_data = bytes([0x02]) + payload
            enc_data = self.encrypt_data(full_data)
            self.cmd_counter += 1
            mac = self.calculate_cmac(self.CMD_CHANGE_FILE_SETTINGS, enc_data)
            final_apdu = enc_data + mac
            
            resp, sw = self.send_apdu(self.CMD_CHANGE_FILE_SETTINGS, data=final_apdu, le=None)
            print(f"  -> SW={hex(sw)}")
            if sw == 0x9000: print("  ✅ SUCCESS!")
        except: pass
        
        # 3. Enc=k1, Mac=k2 (No Le, Payload 00 00 00)
        print("\nTesting Enc=k1, Mac=k2 (No Le, Payload 00 00 00)...")
        try:
            self.authenticate(0, "00000000000000000000000000000000")
            self.key_enc = self.last_k1
            self.key_mac = self.last_k2
            
            payload = bytes.fromhex("00 00 00")
            full_data = bytes([0x02]) + payload
            enc_data = self.encrypt_data(full_data)
            self.cmd_counter += 1
            mac = self.calculate_cmac(self.CMD_CHANGE_FILE_SETTINGS, enc_data)
            final_apdu = enc_data + mac
            
            resp, sw = self.send_apdu(self.CMD_CHANGE_FILE_SETTINGS, data=final_apdu, le=None)
            print(f"  -> SW={hex(sw)}")
            if sw == 0x9000: print("  ✅ SUCCESS!")
        except: pass

if __name__ == "__main__":
    tester = SDMTester()
    tester.connect()
    
    tester.probe_no_le_variants()
