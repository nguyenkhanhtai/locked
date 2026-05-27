from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
import uvicorn
import threading
from contextlib import asynccontextmanager
import uiautomation as auto
import time
from database import BlockedDatabase, ConsumptionDatabase
import urllib.parse
import json
import keyboard
import os
import multiprocessing
import queue
import ctypes
from ctypes import wintypes


def _run_popup(title, url, width, height):
    """
    Mở một cửa sổ browser (pywebview) độc lập để hiển thị popup UI.

    Args:
        title (str): Tiêu đề cửa sổ.
        url (str): URL trỏ tới trang HTML nội bộ (Starlette static).
        width (int): Chiều rộng popup.
        height (int): Chiều cao popup.
    """
    import webview

    class Api:
        def close(self):
            active_win = webview.active_window()
            if active_win:
                active_win.destroy()

    webview.create_window(title, url, js_api=Api(), width=width, height=height, x=400, y=100)
    webview.start()


class Observer:
    """
    Tracks browser activity, manages screen time, and handles website blocking.

    Event-driven design:
    - Hotkeys enqueue actions (no polling delay).
    - Foreground window changes are detected via WinEvent hook (fallback to timer polling).
    - URL checks run only while Chrome is foreground (timer-based, no busy loop).
    """

    def __init__(self):
        """
        Khởi tạo DB + trạng thái + các primitive đồng bộ.

        Luồng tổng quan:
        - Hotkeys được register ngay khi tạo Observer.
        - `start()` sẽ spawn các thread:
          - Hotkey dispatcher: chờ event rồi xử lý queue.
          - WinEvent loop: nhận event foreground-change từ Windows.
        """
        self.db = BlockedDatabase()
        self.consumption_db = ConsumptionDatabase()

        self.current_active_domain = None
        self.domain_time_counter = 0

        self.hotkeys_hooks = {}
        self.last_settings_mtime = 0
        self.settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user", "state.json")

        self._url_lock = threading.Lock()
        self.last_known_url = None

        self._hotkey_actions = queue.SimpleQueue()
        self._hotkey_event = threading.Event()
        self._stop_event = threading.Event()

        self._chrome_active = False
        self._url_poll_timer = None
        self._foreground_poll_timer = None

        self._win_event_hook = None
        self._win_event_proc = None
        self._win_event_thread = None
        self._hotkey_thread = None

        # Register hotkeys ASAP (no waiting for any background timers).
        self.reload_hotkeys()

    def _enqueue_hotkey_action(self, action: str, payload=None):
        """
        Callback hotkey (từ thư viện `keyboard`).

        Nguyên tắc: callback phải thật nhẹ, không block:
        - Đẩy (action, payload) vào queue
        - Set event để đánh thức dispatcher thread
        """
        self._hotkey_actions.put((action, payload))
        self._hotkey_event.set()

    def _get_last_known_url(self):
        """Đọc URL gần nhất (thread-safe)."""
        with self._url_lock:
            return self.last_known_url

    def _set_last_known_url(self, url):
        """Ghi URL gần nhất (thread-safe)."""
        with self._url_lock:
            self.last_known_url = url

    def reload_hotkeys(self):
        """
        Reloads hotkey configs from `state.json` (only when file changes) and re-registers listeners.
        Hotkey callbacks only enqueue actions; a dispatcher thread processes them.
        """
        try:
            if os.path.exists(self.settings_path):
                mtime = os.path.getmtime(self.settings_path)
                if mtime <= self.last_settings_mtime:
                    return
                self.last_settings_mtime = mtime
                with open(self.settings_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)
            else:
                settings = {
                    "hotkeys": {
                        "block": "ctrl+alt+shift+b",
                        "task": "ctrl+alt+shift+t",
                        "memorize": "ctrl+alt+shift+m",
                    }
                }

            hotkeys = settings.get(
                "hotkeys",
                {"block": "ctrl+alt+shift+b", "task": "ctrl+alt+shift+t", "memorize": "ctrl+alt+shift+m"},
            )

            for _, hook in self.hotkeys_hooks.items():
                try:
                    keyboard.remove_hotkey(hook)
                except Exception:
                    pass

            self.hotkeys_hooks.clear()

            if hotkeys.get("block"):
                self.hotkeys_hooks["block"] = keyboard.add_hotkey(
                    hotkeys["block"], lambda: self._enqueue_hotkey_action("block", self._get_last_known_url())
                )
            if hotkeys.get("task"):
                self.hotkeys_hooks["task"] = keyboard.add_hotkey(hotkeys["task"], lambda: self._enqueue_hotkey_action("task"))
            if hotkeys.get("memorize"):
                self.hotkeys_hooks["memorize"] = keyboard.add_hotkey(
                    hotkeys["memorize"], lambda: self._enqueue_hotkey_action("memorize")
                )
        except Exception as e:
            print(f"❌ Hotkeys update error: {e}")

    def trigger_block_popup(self, current_url):
        """Mở popup Quick Block và prefill URL hiện tại."""
        encoded_url = urllib.parse.quote(current_url)
        url = f"http://127.0.0.1:8765/static/popup/block.html?url={encoded_url}"
        multiprocessing.Process(target=_run_popup, args=("Locked - Quick Block", url, 700, 750)).start()

    def trigger_task_popup(self):
        """Mở popup Quick Task."""
        url = "http://127.0.0.1:8765/static/popup/task.html"
        multiprocessing.Process(target=_run_popup, args=("Locked - Quick Task", url, 700, 750)).start()

    def trigger_memorize_popup(self):
        """Mở popup Quick Flashcard."""
        url = "http://127.0.0.1:8765/static/popup/memorize.html"
        multiprocessing.Process(target=_run_popup, args=("Locked - Quick Flashcard", url, 700, 750)).start()

    def get_domain(self, url: str) -> str:
        """
        Lấy "main domain" từ URL.
        Ví dụ: https://www.youtube.com/watch -> youtube
        """
        if not url.startswith(("http://", "https://")):
            url = "http://" + url
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc
        if domain.startswith("www."):
            domain = domain[4:]
        parts = domain.split(".")
        if len(parts) > 1:
            if len(parts) > 2 and parts[-2] in ["com", "co", "edu", "gov", "net", "org"]:
                domain = ".".join(parts[:-2])
            else:
                domain = ".".join(parts[:-1])
        return domain

    def _process_hotkey_actions(self):
        """
        Xử lý toàn bộ action đang chờ trong queue hotkey.

        Chạy trong thread dispatcher (không phải thread UIAutomation/WinEvent).
        """
        while True:
            try:
                action, payload = self._hotkey_actions.get_nowait()
            except Exception:
                break

            if action == "task":
                self.trigger_task_popup()
            elif action == "memorize":
                self.trigger_memorize_popup()
            elif action == "block":
                if payload:
                    self.trigger_block_popup(payload)
                else:
                    print("⚠️ Cần mở cửa sổ trình duyệt trước khi dùng Hotkey!")

        self._hotkey_event.clear()

    def _hotkey_dispatch_loop(self):
        """
        Thread loop:
        - Chờ `_hotkey_event` (được set bởi callback của `keyboard`)
        - Drain queue và thực thi action
        """
        while not self._stop_event.is_set():
            self._hotkey_event.wait()
            if self._stop_event.is_set():
                break
            try:
                self._process_hotkey_actions()
            except Exception as e:
                print(f"❌ hotkey_dispatch error: {e}")

    def _tick_url_check(self):
        """
        Timer tick (~1s) chỉ chạy khi Chrome đang là foreground.
        """
        if self._stop_event.is_set() or not self._chrome_active:
            return

        # Khởi tạo COM cho thread hiện tại (quan trọng để tránh lỗi subscribers)
        _com_init = auto.UIAutomationInitializerInThread()

        try:
            self.reload_hotkeys()

            active_window = auto.GetForegroundControl()
            if not active_window or active_window.ClassName != "Chrome_WidgetWin_1":
                self._chrome_active = False
                return

            # Tìm thanh địa chỉ (Omnibox) một cách tối ưu hơn
            # Chrome thường dùng ClassName 'OmniboxViewViews' cho thanh địa chỉ
            address_bar = active_window.EditControl(depth=None, ClassName="OmniboxViewViews")
            
            # Fallback nếu không tìm thấy theo ClassName (tùy version Chrome)
            if not address_bar.Exists(0, 0):
                address_bar = active_window.EditControl()
                
            if not address_bar.Exists(0, 0):
                return

            # Lấy giá trị URL
            val_pattern = address_bar.GetValuePattern()
            if not val_pattern:
                return
                
            current_url = val_pattern.Value
            self._set_last_known_url(current_url if current_url else None)

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

            current_url_lower = (current_url or "").lower()
            if current_url_lower and "127.0.0.1:8765/static/page/blocked.html" not in current_url_lower:
                block_info = self.db.check_blocked_url(current_url_lower)
                if block_info.get("is_blocked"):
                    redirect_url = (
                        "http://127.0.0.1:8765/static/page/blocked.html"
                        f"?url={urllib.parse.quote(block_info['domain'])}"
                        f"&unlock={block_info['unlock_at']}&mode={block_info['type']}"
                    )
                    auto.SetClipboardText(redirect_url)
                    active_window.SendKeys("{Ctrl}l")
                    time.sleep(0.1)
                    active_window.SendKeys("{Ctrl}v{Enter}")
        except Exception as e:
            # Chỉ in lỗi nếu không phải là lỗi COM tạm thời (subscribers failed)
            err_str = str(e)
            if "-2147220991" not in err_str:
                print(f"❌ url_check error: {e}")
        finally:
            # Giải phóng COM init
            del _com_init
            
            if not self._stop_event.is_set() and self._chrome_active:
                self._url_poll_timer = threading.Timer(1.0, self._tick_url_check)
                self._url_poll_timer.daemon = True
                self._url_poll_timer.start()

    def _set_chrome_active(self, is_active: bool):
        """
        Cập nhật trạng thái "Chrome đang foreground".

        Khi chuyển False -> True thì kick-off `_tick_url_check()` để bắt đầu theo dõi URL.
        """
        if is_active and not self._chrome_active:
            self._chrome_active = True
            self._tick_url_check()
        elif not is_active and self._chrome_active:
            self._chrome_active = False

    def _tick_foreground_check(self):
        """
        Fallback (khi WinEvent hook fail):
        - Mỗi 1s kiểm tra foreground window là Chrome hay không.
        - Implement bằng `threading.Timer` để tránh busy-loop.
        """
        if self._stop_event.is_set():
            return

        try:
            ctrl = auto.GetForegroundControl()
            self._set_chrome_active(bool(ctrl and ctrl.ClassName == "Chrome_WidgetWin_1"))
        except Exception:
            pass
        finally:
            if not self._stop_event.is_set():
                self._foreground_poll_timer = threading.Timer(1.0, self._tick_foreground_check)
                self._foreground_poll_timer.daemon = True
                self._foreground_poll_timer.start()

    def _start_foreground_polling_fallback(self):
        """Start fallback foreground polling (chỉ start 1 lần)."""
        if self._foreground_poll_timer:
            return
        self._tick_foreground_check()

    def _run_win_event_loop(self):
        """
        Thread WinEvent hook:
        - Hook foreground-change (EVENT_SYSTEM_FOREGROUND).
        - Message loop để nhận callback.

        Nếu hook fail thì fallback sang `_start_foreground_polling_fallback()`.
        """
        _ = auto.UIAutomationInitializerInThread()

        user32 = ctypes.windll.user32

        EVENT_SYSTEM_FOREGROUND = 0x0003
        WINEVENT_OUTOFCONTEXT = 0x0000

        WinEventProcType = ctypes.WINFUNCTYPE(
            None,
            wintypes.HANDLE,  # HWINEVENTHOOK is a HANDLE; wintypes doesn't expose HWINEVENTHOOK
            wintypes.DWORD,
            wintypes.HWND,
            wintypes.LONG,
            wintypes.LONG,
            wintypes.DWORD,
            wintypes.DWORD,
        )

        def _callback(hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
            try:
                ctrl = auto.GetForegroundControl()
                self._set_chrome_active(bool(ctrl and ctrl.ClassName == "Chrome_WidgetWin_1"))
            except Exception:
                pass

        self._win_event_proc = WinEventProcType(_callback)
        hook = user32.SetWinEventHook(
            EVENT_SYSTEM_FOREGROUND,
            EVENT_SYSTEM_FOREGROUND,
            0,
            self._win_event_proc,
            0,
            0,
            WINEVENT_OUTOFCONTEXT,
        )
        if not hook:
            print("⚠️ WinEvent hook failed; using timer-based foreground polling fallback.")
            self._start_foreground_polling_fallback()
            return

        self._win_event_hook = hook

        msg = wintypes.MSG()
        while not self._stop_event.is_set() and user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        try:
            user32.UnhookWinEvent(self._win_event_hook)
        except Exception:
            pass

    def start(self):
        """
        Khởi chạy Observer background workers.

        Gọi từ Starlette lifespan (khi server start).
        """
        self._stop_event.clear()

        self._hotkey_thread = threading.Thread(target=self._hotkey_dispatch_loop, daemon=True)
        self._hotkey_thread.start()

        self._win_event_thread = threading.Thread(target=self._run_win_event_loop, daemon=True)
        self._win_event_thread.start()


async def homepage(request):
    """Health-check endpoint."""
    return JSONResponse({"status": "Observer background listeners running!"})


routes = [
    Route("/", endpoint=homepage),
]


@asynccontextmanager
async def lifespan(app):
    observer = Observer()
    observer.start()
    yield


app = Starlette(debug=True, routes=routes, lifespan=lifespan)


if __name__ == "__main__":
    uvicorn.run("observer:app", host="127.0.0.1", port=8766, reload=True)
