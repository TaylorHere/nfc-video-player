import tkinter as tk
from tkinter import messagebox, scrolledtext
import threading
import sys
import os

# Add local directory to path to find ntag424_manager
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from ntag424_manager import Ntag424DNA
except ImportError:
    Ntag424DNA = None

class NFCWriterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NFC Card Writer - NTAG 424 DNA")
        self.root.geometry("600x480")
        
        # Style
        self.bg_color = "#f0f0f0"
        self.root.configure(bg=self.bg_color)

        # Title
        tk.Label(root, text="NFC 写卡工具 (Windows)", font=("Segoe UI", 16, "bold"), bg=self.bg_color).pack(pady=10)

        # Input Frame
        input_frame = tk.Frame(root, bg=self.bg_color)
        input_frame.pack(pady=10, padx=20, fill="x")

        tk.Label(input_frame, text="Base URL:", bg=self.bg_color, font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w")
        self.url_entry = tk.Entry(input_frame, width=50, font=("Segoe UI", 10))
        self.url_entry.grid(row=0, column=1, padx=10)
        self.url_entry.insert(0, "https://deo.app/nfc")

        # Status/Log
        self.log_area = scrolledtext.ScrolledText(root, height=15, width=70, state='disabled', font=("Consolas", 9))
        self.log_area.pack(pady=10, padx=20)

        # Buttons
        btn_frame = tk.Frame(root, bg=self.bg_color)
        btn_frame.pack(pady=10)

        self.write_btn = tk.Button(btn_frame, text="开始写卡", command=self.start_writing, 
                                 bg="#0078D7", fg="white", font=("Segoe UI", 11, "bold"), padx=20, pady=5, relief="flat")
        self.write_btn.pack(side="left", padx=10)

        self.clear_btn = tk.Button(btn_frame, text="清空日志", command=self.clear_log,
                                 bg="#9E9E9E", fg="white", font=("Segoe UI", 10), relief="flat")
        self.clear_btn.pack(side="left", padx=10)

        self.log("准备就绪。请连接读卡器并放入卡片。")

    def log(self, message):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    def clear_log(self):
        self.log_area.config(state='normal')
        self.log_area.delete(1.0, tk.END)
        self.log_area.config(state='disabled')

    def start_writing(self):
        url_base = self.url_entry.get().strip()
        if not url_base:
            messagebox.showerror("错误", "请输入 Base URL")
            return
        
        self.write_btn.config(state="disabled", text="写入中...")
        threading.Thread(target=self.write_process, args=(url_base,), daemon=True).start()

    def write_process(self, url_base):
        try:
            if Ntag424DNA is None:
                self.log("错误: 找不到 ntag424_manager 模块。请确保文件完整。")
                return

            self.log(f"正在连接读卡器...")
            
            # Initialize Logic
            tag = Ntag424DNA()
            try:
                tag.connect()
                self.log("读卡器连接成功，正在寻找卡片...")
                
                # 1. Auth
                self.log("正在认证 (默认密钥)...")
                tag.authenticate(0, "00000000000000000000000000000000")
                
                # 2. Construct NDEF
                p_placeholder = "0" * 32
                m_placeholder = "0" * 16
                
                separator = "?" if "?" not in url_base else "&"
                full_url = f"{url_base}{separator}p={p_placeholder}&m={m_placeholder}"
                
                self.log(f"写入 URL: {full_url}")
                tag.write_ndef(full_url)
                
                # 3. Calculate Offsets (Dynamic)
                # File Header (2) + NDEF Msg Header (4: D1 01 Len 55) = 6 bytes? 
                # Wait, ntag424_manager.write_ndef does:
                # prefix = 0x00
                # payload = 00 + url_utf8
                # ndef_msg = D1 01 len(payload) 55 + payload
                # file_data = len(ndef_msg)(2) + ndef_msg
                
                # Indices in file_data:
                # 0-1: File Len
                # 2: D1
                # 3: 01
                # 4: Len(Payload)
                # 5: 55 ('U')
                # 6: 00 (URI Prefix 'None')
                # 7: URL Start
                
                url_start_offset = 7
                
                # Find 'p=' position in full_url
                try:
                    p_index = full_url.index("p=" + p_placeholder)
                    # We need the VALUE of p, not 'p='
                    p_value_index = p_index + 2 # length of 'p='
                    
                    picc_offset = url_start_offset + p_value_index
                    
                    # Find 'm=' position
                    m_index = full_url.index("m=" + m_placeholder)
                    m_value_index = m_index + 2
                    
                    mac_offset = url_start_offset + m_value_index
                    
                    self.log(f"计算偏移量: P={picc_offset}, M={mac_offset}")
                    
                    tag.setup_sdm(picc_offset=picc_offset, mac_offset=mac_offset)
                    self.log("启用 SDM (动态计算偏移)...")
                    
                    self.log("✅ 写入成功！请移开卡片。")
                    
                except ValueError:
                    self.log("⚠️ 无法在 URL 中找到 p= 或 m= 参数，跳过 SDM 配置。")
                
            except Exception as e:
                self.log(f"❌ 操作失败: {e}")
                import traceback
                traceback.print_exc()
                
        except Exception as e:
             self.log(f"系统错误: {e}")
        finally:
            self.root.after(0, self.reset_btn)

    def reset_btn(self):
        self.write_btn.config(state="normal", text="开始写卡")

if __name__ == "__main__":
    root = tk.Tk()
    app = NFCWriterApp(root)
    root.mainloop()
