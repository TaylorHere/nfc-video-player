import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
import sys
import os
import struct

try:
    from ntag424_manager import Ntag424DNA
except ImportError:
    Ntag424DNA = None

try:
    from app_crypto import encrypt_url_for_app
except ImportError:
    encrypt_url_for_app = None

class NFCWriterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NFC Video Player Writer Tool v2.2 (Fix SDM+Read)")
        self.root.geometry("600x700")
        
        # Style
        self.bg_color = "#f0f0f0"
        self.root.configure(bg=self.bg_color)
        
        # Style Config
        style = ttk.Style()
        style.configure("TNotebook", background=self.bg_color)
        style.configure("TFrame", background=self.bg_color)

        # Title
        tk.Label(root, text="NFC 写卡工具 (Windows)", font=("Segoe UI", 16, "bold"), bg=self.bg_color).pack(pady=10)

        # Input Frame
        input_frame = tk.Frame(root, bg=self.bg_color)
        input_frame.pack(pady=10, padx=20, fill="x")

        tk.Label(input_frame, text="URL:", bg=self.bg_color, font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w")
        self.url_entry = tk.Entry(input_frame, width=50, font=("Segoe UI", 10))
        self.url_entry.grid(row=0, column=1, padx=10)
        # Default to a local backend verify URL for SUN mode demo
        self.url_entry.insert(0, "http://192.168.1.100:8000/verify") 
        
        # Options Frame
        opts_frame = tk.Frame(root, bg=self.bg_color)
        opts_frame.pack(pady=5)
        
        self.mode_var = tk.StringVar(value="sun")
        
        rb1 = tk.Radiobutton(opts_frame, text="普通链接", variable=self.mode_var, value="plain", bg=self.bg_color)
        rb2 = tk.Radiobutton(opts_frame, text="App 加密 (AES)", variable=self.mode_var, value="encrypt", bg=self.bg_color)
        rb3 = tk.Radiobutton(opts_frame, text="NTAG 424 SUN (防伪+唯一)", variable=self.mode_var, value="sun", bg=self.bg_color)
        
        rb1.pack(side="left", padx=10)
        rb2.pack(side="left", padx=10)
        rb3.pack(side="left", padx=10)

        # Batch Checkbox
        self.batch_var = tk.BooleanVar(value=False)
        tk.Checkbutton(root, text="批量连续写入模式 (自动检测新卡)", variable=self.batch_var, bg=self.bg_color).pack(pady=5)

        # Status/Log
        self.log_area = scrolledtext.ScrolledText(root, height=15, width=75, state='disabled', font=("Consolas", 9))
        self.log_area.pack(pady=10, padx=20)

        # Buttons
        btn_frame = tk.Frame(root, bg=self.bg_color)
        btn_frame.pack(pady=10)

        self.write_btn = tk.Button(btn_frame, text="开始写卡", command=self.toggle_writing, 
                                 bg="#0078D7", fg="white", font=("Segoe UI", 11, "bold"), padx=20, pady=5, relief="flat")
        self.write_btn.pack(side="left", padx=10)

        self.read_btn = tk.Button(btn_frame, text="读取卡片", command=self.read_card,
                                 bg="#28a745", fg="white", font=("Segoe UI", 11, "bold"), padx=20, pady=5, relief="flat")
        self.read_btn.pack(side="left", padx=10)

        self.clear_btn = tk.Button(btn_frame, text="清空日志", command=self.clear_log,
                                 bg="#9E9E9E", fg="white", font=("Segoe UI", 10), relief="flat")
        self.clear_btn.pack(side="left", padx=10)

        self.log("准备就绪。请选择模式并点击开始。")
        self.log("注意：SUN 模式现在将配置为 '明文 UID + CMAC' 模式，以支持手机免密读取。")
        self.is_running = False

    def log(self, message):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    def clear_log(self):
        self.log_area.config(state='normal')
        self.log_area.delete(1.0, tk.END)
        self.log_area.config(state='disabled')

    def read_card(self):
        self.log("正在读取卡片...")
        threading.Thread(target=self._read_thread, daemon=True).start()

    def _read_thread(self):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if Ntag424DNA is None:
                    self.log("错误: 找不到 ntag424_manager 模块。")
                    return

                tag = Ntag424DNA()
                try:
                    tag.connect()
                    # 尝试读取 NDEF
                    # 1. Get File Settings for File 2 to confirm it exists and get size
                    self.log(f"检查文件 2 设置 (尝试 {attempt+1}/{max_retries})...")
                    file_settings, sw_fs = tag.get_file_settings(2)
                
                    if file_settings:
                        # Log raw settings for debug
                        self.log(f"DEBUG: FileSettings={file_settings.hex()}")
                        
                        # Check SDM
                        file_option = file_settings[1]
                        if file_option & 0x40:
                             self.log("DEBUG: SDM 启用 (Bit 6=1)")
                        else:
                             self.log("DEBUG: SDM 未启用 (Bit 6=0)")

                        # 2. Read Data
                        # Parse file size from settings (Bytes 4-6, Little Endian)
                        # FileType(1) Option(1) Access(2) Size(3)
                        if len(file_settings) >= 7:
                            file_size = struct.unpack("<I", file_settings[4:7] + b'\x00')[0]
                            self.log(f"文件大小: {file_size} 字节")
                        else:
                            file_size = 0 # Fallback to 0 (all)
                
                # Native ReadData: Cmd 0xAD.
                        # Data: FileNo(1) | Offset(3) | Length(3)
                        
                        # Construct ReadData command with explicit length
                        # Try reading smaller chunks first
                        self.log("尝试读取文件头部 (32 bytes)...")
                        read_len_bytes = struct.pack("<I", 32)[:3]
                        read_data_cmd = bytes([0x02, 0x00, 0x00, 0x00]) + read_len_bytes
                
                        resp, sw = tag.send_apdu(0xAD, read_data_cmd)
                
                        if sw == 0x9000 or sw == 0x9100:
                            data = bytes(resp)
                            self.log(f"头部读取成功: {data.hex()[:20]}...")
                            # Read rest
                            if file_size > 32:
                                self.log("读取剩余部分...")
                                read_len_bytes = struct.pack("<I", file_size - 32)[:3]
                                # Offset 32
                                read_data_cmd = bytes([0x02, 0x20, 0x00, 0x00]) + read_len_bytes
                                resp2, sw2 = tag.send_apdu(0xAD, read_data_cmd)
                                if sw2 == 0x9000 or sw2 == 0x9100:
                                    data += bytes(resp2)
                            
                            self.log(f"读取完成 ({len(data)} bytes)")
                            self._parse_ndef(data)
                            return # Success
                        elif sw == 0:
                             self.log(f"读取超时或无响应 (SW=0000)。")
                        elif sw == 0x6982: # Security Status Not Satisfied
                             self.log(f"读取失败: 需要认证 (SW=6982)")
                             # Maybe try to authenticate with Key 0 and read?
                             # But we want public read. If failed, it means Access Rights are wrong.
                        else:
                            self.log(f"读取失败: SW={hex(sw)}")
                    else:
                        self.log(f"无法获取文件 2 设置 (SW={hex(sw_fs)})，尝试 ISO 读取...")
                        self._read_iso_fallback(tag)
                        return # Only try fallback once per attempt loop?

                except Exception as e:
                    self.log(f"读取异常: {e}")
                    if "80100068" in str(e) or "reset" in str(e).lower():
                        self.log("检测到卡片重置，正在重试...")
                        time.sleep(1.0)
                        continue # Retry loop
                    # If not a reset error, break or continue?
                    # Let's try ISO fallback if native failed unexpectedly?
                    # self._read_iso_fallback(tag) 
            except Exception as e:
                self.log(f"系统异常: {e}")
            
            # If we reached here without returning, wait a bit before retry (if loop continues)
            time.sleep(0.5)
        
        self.log("读取操作最终失败。")

    def _read_iso_fallback(self, tag):
        try:
            self.log("尝试 ISO 7816-4 读取 (NDEF)...")
            if hasattr(tag, 'connection'):
                # Select File E104 (NDEF)
                apdu_select = [0x00, 0xA4, 0x00, 0x0C, 0x02, 0xE1, 0x04]
                resp, sw1, sw2 = tag.connection.transmit(apdu_select)
                sw = (sw1 << 8) | sw2
                if sw == 0x9000:
                    self.log("ISO Select E104 成功")
                    # Read Binary (Read 256 bytes)
                    apdu_read = [0x00, 0xB0, 0x00, 0x00, 0x00]
                    resp, sw1, sw2 = tag.connection.transmit(apdu_read)
                    sw = (sw1 << 8) | sw2
                    if sw == 0x9000:
                        data = bytes(resp)
                        self.log(f"ISO 读取成功 ({len(data)} bytes)")
                        self._parse_ndef(data)
                    else:
                        self.log(f"ISO Read Binary 失败: SW={hex(sw)}")
                else:
                    self.log(f"ISO Select E104 失败: SW={hex(sw)}")
            else:
                self.log("无法访问底层连接进行 ISO 读取")
        except Exception as e:
            self.log(f"ISO 读取异常: {e}")

    def _parse_ndef(self, data):
        # 解析 NDEF
        if len(data) > 2:
            ndef_len = (data[0] << 8) | data[1]
            self.log(f"NDEF 长度: {ndef_len}")
            
            if ndef_len > len(data) - 2:
                self.log("警告: 数据不完整，可能需要读取更多数据")
                ndef_msg = data[2:]
            else:
                ndef_msg = data[2:2+ndef_len]
            
            # 简单的 NDEF 解析 (假设是 URI Record)
            if len(ndef_msg) > 4 and ndef_msg[0] == 0xD1:
                payload_len = ndef_msg[2]
                if ndef_msg[3] == 0x55: # 'U'
                    prefix_byte = ndef_msg[4]
                    prefixes = ["", "http://www.", "https://www.", "http://", "https://", "tel:", "mailto:", "ftp://anonymous:anonymous@", "ftp://ftp.", "ftps://", "sftp://", "smb://", "nfs://", "ftp://", "dav://", "news:", "telnet://", "imap:", "rtsp://", "urn:", "pop:", "sip:", "sips:", "tftp:", "btspp://", "btl2cap://", "btgoep://", "tcpobex://", "irdaobex://", "file://", "urn:epc:id:", "urn:epc:tag:", "urn:epc:pat:", "urn:epc:raw:", "urn:epc:", "urn:nfc:"]
                    prefix = prefixes[prefix_byte] if prefix_byte < len(prefixes) else ""
                    url_content = ndef_msg[5:5+payload_len-1].decode('utf-8', errors='ignore')
                    full_url = prefix + url_content
                    self.log(f"NDEF URL: {full_url}")
                    
                    if "p=" in full_url:
                        p_val = full_url.split("p=")[1].split("&")[0]
                        self.log(f"参数 p: {p_val}")
                    if "m=" in full_url:
                        m_val = full_url.split("m=")[1].split("&")[0]
                        self.log(f"参数 m: {m_val}")
                else:
                    self.log(f"非 URI 记录 (Type: {ndef_msg[3]:02X})")
                    self.log(f"Hex: {ndef_msg.hex()}")
            else:
                self.log("无法解析 NDEF 记录")
                self.log(f"Hex: {data.hex()[:100]}...")

    def toggle_writing(self):
        if self.is_running:
            self.is_running = False
            self.write_btn.config(text="停止中...", state="disabled")
            return

        url_input = self.url_entry.get().strip()
        if not url_input:
            messagebox.showerror("错误", "请输入 URL")
            return
        
        self.is_running = True
        self.write_btn.config(text="停止写入", bg="#d9534f")
        
        mode = self.mode_var.get()
        is_batch = self.batch_var.get()
        
        threading.Thread(target=self.write_loop, args=(url_input, mode, is_batch), daemon=True).start()

    def write_loop(self, url_input, mode, is_batch):
        while self.is_running:
            self.write_one_card(url_input, mode)
            
            if not is_batch:
                break
            
            if self.is_running:
                self.log(">>> 等待下一张卡片 (请先移开当前卡)...")
                time.sleep(2) # Simple debounce
                # Ideally we should wait until reader is empty, then wait for card insertion
                # But simple delay works for manual operation
        
        self.is_running = False
        self.root.after(0, self.reset_ui)

    def write_one_card(self, url_input, mode):
        try:
            if Ntag424DNA is None:
                self.log("错误: 找不到 ntag424_manager 模块。")
                self.is_running = False
                return

            # Process URL based on mode
            final_url = url_input
            
            if mode == "encrypt":
                if encrypt_url_for_app:
                    try:
                        final_url = encrypt_url_for_app(url_input)
                        self.log(f"已加密 URL: {final_url[:30]}...")
                    except Exception as e:
                        self.log(f"加密失败: {e}")
                        return
                else:
                    self.log("错误: 找不到 app_crypto 模块，无法加密。")
                    return
            elif mode == "sun":
                if "p=" not in url_input and "m=" not in url_input:
                    separator = "?" if "?" not in url_input else "&"
                    # p=32 chars hex (16 bytes) -> encrypted data (32 bytes = 64 hex chars?)
                    # Wait, SDMENCLength is 32 bytes. Hex string is 64 chars.
                    # My placeholder "0"*32 is only 16 bytes (32 hex chars).
                    # I need 32 bytes placeholder -> 64 hex chars.
                    p_placeholder = "0" * 64
                    m_placeholder = "0" * 16 # CMAC is 8 bytes -> 16 hex chars
                    final_url = f"{url_input}{separator}p={p_placeholder}&m={m_placeholder}"
                    self.log(f"已自动添加 SUN 参数模板")

            self.log(f"正在扫描卡片...")
            
            # Initialize Logic
            tag = Ntag424DNA()
            try:
                tag.connect()
                # self.log("卡片已连接。")
                
                # 1. Auth
                self.log("认证 (Key 0)...")
                tag.authenticate(0, "00000000000000000000000000000000")
                
                # 2. Write NDEF
                self.log(f"写入数据...")
                # 注意：WriteData (Plain) 可能会导致 EV2 会话失效，
                # 因此我们在写完数据后需要重新认证才能进行 ChangeFileSettings。
                tag.write_ndef(final_url)
                
                # 3. Configure SDM only if mode is SUN
                if mode == "sun":
                    self.log("重新认证以配置 SDM...")
                    tag.authenticate(0, "00000000000000000000000000000000")
                    p_placeholder = "0" * 64
                    m_placeholder = "0" * 16
                    
                    url_start_offset = 7
                    
                    # Find 'p=' position in full_url
                    try:
                        p_index = final_url.index("p=" + p_placeholder)
                        p_value_index = p_index + 2
                        picc_offset = url_start_offset + p_value_index
                        
                        m_index = final_url.index("m=" + m_placeholder)
                        m_value_index = m_index + 2
                        mac_offset = url_start_offset + m_value_index
                        
                        self.log(f"DEBUG: P_Offset={picc_offset}, M_Offset={mac_offset}")
                        
                        # Use 0x80 (UID Mirror Only) - Adjusted for compatibility
                        try:
                            tag.enable_sdm(picc_offset=picc_offset, mac_offset=mac_offset)
                            self.log(f"✅ SUN 防伪启用成功!")
                        except Exception as e:
                            self.log(f"❌ 启用 SUN 防伪失败: {e}")
                            return

                    except ValueError:
                        self.log("错误: URL 格式不包含 p= 或 m= 参数，无法配置 SUN。")
                        return

                self.log(f"✅ 写入成功! URL: `{final_url}` ")
                self.log(f"请移开卡片。")
                
                # If batch mode, loop will continue. 
                # To prevent re-writing same card immediately, we should ideally wait for removal.
                while True:
                     if not self.is_running: break
                     try:
                         # Wait for card removal
                         tag.connect()
                         time.sleep(0.5)
                     except:
                         # Card removed
                         break
                
            except Exception as e:
                # If no card found, just ignore and retry in loop
                if "No NFC reader" in str(e) or "No card found" in str(e):
                    # self.log("等待卡片...")
                    pass
                else:
                    self.log(f"❌ 失败: {e}")
                
                time.sleep(1) # Wait before retry
                
        except Exception as e:
             self.log(f"系统错误: {e}")

    def reset_ui(self):
        self.write_btn.config(state="normal", text="开始写卡", bg="#0078D7")


if __name__ == "__main__":
    root = tk.Tk()
    app = NFCWriterApp(root)
    root.mainloop()
