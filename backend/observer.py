from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from datetime import datetime
import uvicorn
import sqlite3
import threading
from contextlib import asynccontextmanager
import uiautomation as auto
import time
from database import BlockedDatabase, ConsumptionDatabase
import urllib.request
import urllib.parse
import json
import keyboard
import os
import multiprocessing

def _run_popup(title, url, width, height):
    """
    Launches an independent embedded browser window (webview) to display a UI popup.
    
    Args:
        title (str): The title of the window.
        url (str): The internal path pointing to the HTML interface.
        width (int): The width of the popup window.
        height (int): The height of the popup window.
    """
    import webview
    
    class Api:
        def close(self):
            # Lấy cửa sổ hiện tại và đóng nó
            active_win = webview.active_window()
            if active_win:
                active_win.destroy()
    
    window = webview.create_window(title, url, js_api=Api(), width=width, height=height, x = 400, y=100)
    
    webview.start()

class Observer:
    """
    Class responsible for tracking browser activity, managing screen time, and handling website blocking in the background.
    """
    def __init__(self):
        """Initializes database connections, hotkey state flags, and settings file configuration."""
        self.db = BlockedDatabase()
        self.consumption_db = ConsumptionDatabase()
        self.hotkey_block_triggered = False
        self.hotkey_task_triggered = False
        self.hotkey_memorize_triggered = False
        self.current_active_domain = None
        self.domain_time_counter = 0
        self.hotkeys_hooks = {}
        self.last_settings_mtime = 0
        self.settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user", "state.json")
        
    def reload_hotkeys(self):
        """
        Reloads the hotkey configurations from the `state.json` file and updates the hotkey listeners.
        This sets the trigger flags to True when the user presses the configured key combinations.
        """
        try:
            if os.path.exists(self.settings_path):
                mtime = os.path.getmtime(self.settings_path)
                if mtime <= self.last_settings_mtime: return
                self.last_settings_mtime = mtime
                with open(self.settings_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
            else:
                settings = {"hotkeys": {"block": "ctrl+alt+shift+b", "task": "ctrl+alt+shift+t", "memorize": "ctrl+alt+shift+m"}}
            
            
            hotkeys = settings.get("hotkeys", {"block": "ctrl+alt+shift+b", "task": "ctrl+alt+shift+t", "memorize": "ctrl+alt+shift+m"})
            
            for key, hook in self.hotkeys_hooks.items():
                try: keyboard.remove_hotkey(hook)
                except Exception: pass
            
            self.hotkeys_hooks.clear()
            
            if hotkeys.get("block"): self.hotkeys_hooks["block"] = keyboard.add_hotkey(hotkeys["block"], lambda: setattr(self, 'hotkey_block_triggered', True))
            if hotkeys.get("task"): self.hotkeys_hooks["task"] = keyboard.add_hotkey(hotkeys["task"], lambda: setattr(self, 'hotkey_task_triggered', True))
            if hotkeys.get("memorize"): self.hotkeys_hooks["memorize"] = keyboard.add_hotkey(hotkeys["memorize"], lambda: setattr(self, 'hotkey_memorize_triggered', True))
        except Exception as e:
            print(f"❌ Hotkeys update error: {e}")

    def trigger_block_popup(self, current_url):
        """
        Triggers the Quick Block popup and preloads the current URL.
        
        Args:
            current_url (str): The URL of the currently active website.
        """
        encoded_url = urllib.parse.quote(current_url)
        url = f"http://127.0.0.1:8765/static/popup/block.html?url={encoded_url}"
        multiprocessing.Process(target=_run_popup, args=("Locked - Quick Block", url, 700, 750)).start()
    
    def trigger_task_popup(self):
        """Triggers the Quick Task management popup window."""
        url = "http://127.0.0.1:8765/static/popup/task.html"
        multiprocessing.Process(target=_run_popup, args=("Locked - Quick Task", url, 700, 750)).start()

    def trigger_memorize_popup(self):
        """Triggers the Quick Flashcard learning popup window."""
        url = "http://127.0.0.1:8765/static/popup/memorize.html"
        multiprocessing.Process(target=_run_popup, args=("Locked - Quick Flashcard", url, 700, 750)).start()

    def get_domain(self, url: str) -> str:
        """
        Extracts and normalizes the main domain from a full URL.
        Ex: 'https://www.youtube.com/watch' -> 'youtube.com'
        """
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc
        if domain.startswith('www.'):
            domain = domain[4:]
        parts = domain.split('.')
        if len(parts) > 1:
            if len(parts) > 2 and parts[-2] in ['com', 'co', 'edu', 'gov', 'net', 'org']:
                domain = '.'.join(parts[:-2])
            else:
                domain = '.'.join(parts[:-1])
        return domain

    # Hàm theo dõi và chặn tab trình duyệt
    def window_listener(self):
        """
        Main background loop of the Observer that listens for the active window.
        
        Functions:
        - Tracks usage time for each domain and saves it to the database.
        - Captures hotkey events to open functionality popups.
        - Detects blocked URLs and redirects the browser tab to an internal notification page.
        """
        # Bắt buộc phải khởi tạo UIAutomation khi sử dụng trong một luồng (thread) phụ
        _ = auto.UIAutomationInitializerInThread()
        
        print("🛡️ Server đang chạy ngầm và theo dõi trình duyệt...")
        
        while True:
            try:
                self.reload_hotkeys()
                
                if self.hotkey_task_triggered:
                    self.hotkey_task_triggered = False
                    self.trigger_task_popup()
                    
                if self.hotkey_memorize_triggered:
                    self.hotkey_memorize_triggered = False
                    self.trigger_memorize_popup()

                active_window = auto.GetForegroundControl()
                if active_window and active_window.ClassName == 'Chrome_WidgetWin_1':
                    address_bar = active_window.EditControl()
                    if address_bar.Exists(0, 0): 
                        current_url = address_bar.GetValuePattern().Value
                        
                        # 0. Theo dõi thời gian sử dụng
                        if current_url:
                            current_domain = self.get_domain(current_url)
                            if current_domain == self.current_active_domain:
                                self.domain_time_counter += 1
                                if self.domain_time_counter >= 10:
                                    self.consumption_db.add_time(self.current_active_domain, 10)
                                    self.domain_time_counter = 0
                            else:
                                self.current_active_domain = current_domain
                                self.domain_time_counter = 1
                        else:
                            self.current_active_domain = None
                            self.domain_time_counter = 0

                        # 1. Xử lý Hotkey Quick Block
                        if self.hotkey_block_triggered:
                            self.hotkey_block_triggered = False
                            if current_url:
                                self.trigger_block_popup(current_url)
                                continue # Bỏ qua logic phía dưới để bắt đầu vòng lặp mới
                        
                        # 2. Xử lý Chặn Tự Động

                        if current_url:
                            current_url = current_url.lower()
                            
                            # Bỏ qua nếu đang ở trang thông báo bị chặn để tránh vòng lặp vô hạn
                            if "127.0.0.1:8765/static/page/aux/blocked.html" not in current_url:
                                block_info = self.db.check_blocked_url(current_url)

                                if block_info.get("is_blocked"):
                                    print(f"\n🚨 Access detected: {current_url}")
                                    print("--> Redirecting to the notification page...")
                                    
                                    # Tạo URL mới
                                    redirect_url = f"http://127.0.0.1:8765/static/page/aux/blocked.html?url={urllib.parse.quote(block_info['domain'])}&unlock={block_info['unlock_at']}&mode={block_info['type']}"
                                    
                                    # Chọn thanh địa chỉ, dán URL mới và nhấn Enter
                                    auto.SetClipboardText(redirect_url)
                                    active_window.SendKeys('{Ctrl}l')
                                    time.sleep(0.1)
                                    active_window.SendKeys('{Ctrl}v{Enter}')
                                    
                                    time.sleep(1)
                
                if self.hotkey_block_triggered:
                    self.hotkey_block_triggered = False
                    print("⚠️ Cần mở cửa sổ trình duyệt trước khi dùng Hotkey!")
                    
                time.sleep(1)
            except Exception:
                pass

# Định nghĩa route cơ bản để tránh lỗi thiếu biến routes
async def homepage(request):
    """Endpoint to check the operational status of the Observer server."""
    return JSONResponse({"status": "Background window listener is running!"})

routes = [
    Route('/', endpoint=homepage)
]

# Khởi chạy luồng (thread) lắng nghe trình duyệt ngay khi server Starlette start
@asynccontextmanager
async def lifespan(app):
    """
    Manages the lifespan of the Starlette application.
    Automatically starts the `window_listener` on an independent background thread upon server startup.
    """
    observer = Observer()
    listener_thread = threading.Thread(target=observer.window_listener, daemon=True)
    listener_thread.start()
    yield

# 3. Khởi tạo ứng dụng
app = Starlette(debug=True, routes=routes, lifespan=lifespan)

# 4. Chạy server bằng Uvicorn
if __name__ == '__main__':
    # Chạy ở port 7500 (port mặc định phổ biến của các framework ASGI)
    uvicorn.run("observer:app", host='127.0.0.1', port=8766, reload=True, use_colors = False)
