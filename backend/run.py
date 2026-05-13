import multiprocessing
import uvicorn
import time
import os
import sys
import subprocess

def run_backend():
    # Chạy app.py (Tắt reload để tránh tạo thêm process con không kiểm soát được)
    uvicorn.run("app:app", host='127.0.0.1', port=8765, reload=False)

def run_observer():
    # Chạy observer.py
    uvicorn.run("observer:app", host='127.0.0.1', port=8766, reload=False)

if __name__ == '__main__':
    # Bắt buộc trên Windows để tránh lỗi vòng lặp khi tạo Process
    multiprocessing.freeze_support()

    # Tự động tách ra một cửa sổ CMD quản lý độc lập nếu chưa có
    if os.environ.get("LOCKED_DETACHED") != "1":
        env = os.environ.copy()
        env["LOCKED_DETACHED"] = "1"
        script_path = os.path.abspath(__file__)
        # Lệnh pop-up ra màn hình CMD mới mang tên "Locked Management"
        command = f'start "Locked Management" cmd /c ""{sys.executable}" "{script_path}" & pause"'
        subprocess.Popen(command, shell=True, env=env)
        sys.exit()

    print("🚀 Starting Locked Backend and Observer...")
    backend_process = multiprocessing.Process(target=run_backend, daemon=True)
    observer_process = multiprocessing.Process(target=run_observer, daemon=True)

    backend_process.start()
    observer_process.start()

    try:
        print("✅ Dịch vụ đang chạy. Truy cập http://localhost:8765 trên trình duyệt của bạn.")
        print("Nhấn Ctrl+C để thoát.")
        # Giữ cho process chính hoạt động
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Nhận lệnh tắt từ người dùng...")
    finally:
        backend_process.terminate()
        observer_process.terminate()
        print("🛑 Đã đóng tất cả dịch vụ Locked.")
