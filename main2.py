import sys
import threading
import tkinter as tk
import requests  # 用于检查后端服务是否启动
from tkinter import messagebox
from ui3 import VideoGeneratorApp  # 确保ui2.py在同一目录

# 全局标志，表示后端是否启动
backend_started = False

def run_flask_server():
    """启动Flask后端服务"""
    global backend_started
    try:
        # 直接调用app.py中的逻辑
        from app import start
        start()  # 调用app.py中的start()函数启动Flask
        backend_started = True  # 设置标志，表示后端已经启动
    except Exception as e:
        print(f"后端启动失败: {str(e)}")
        sys.exit(1)

def check_backend_status():
    """检查后端服务是否已启动"""
    global backend_started
    try:
        # 检查后端是否已响应
        response = requests.get("http://127.0.0.1:5000/progress/<task_id>")
        if response.status_code == 200:
            backend_started = True  # 如果返回200，表示后端已启动
    except requests.ConnectionError:
        pass  # 后端尚未启动，忽略错误

def run_tkinter_gui():
    global backend_started
    """启动Tkinter前端界面"""
    try:
        root = tk.Tk()
        loading_label = tk.Label(root, text="正在启动，请稍候...", font=("Arial", 14))
        loading_label.pack(pady=50)

        # 动画更新函数
        def update_loading_animation():
            """更新等待动画"""
            if not backend_started:
                text = loading_label.cget("text")
                if text.endswith("..."):
                    loading_label.config(text="正在启动，请稍候")
                else:
                    loading_label.config(text="正在启动，请稍候...")

                # 每500毫秒更新一次
                root.after(500, update_loading_animation)

        # 启动等待动画
        update_loading_animation()

        # 定期检查后端是否启动并更新界面
        def check_backend_and_stop_animation():
            if backend_started:
                loading_label.config(text="已启动，正在加载界面...")
                loading_label.destroy()
                app = VideoGeneratorApp(root)
                root.mainloop()  # 启动Tkinter主循环，保持主线程不退出
            else:
                # 如果后端未启动，继续检查
                check_backend_status()
                # 每秒检查一次
                root.after(1000, check_backend_and_stop_animation)

        # 启动检查后端状态的函数
        check_backend_and_stop_animation()

        # 启动Tkinter的事件循环，保持主线程不退出
        root.mainloop()

    except Exception as e:
        print(f"前端启动失败: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    # 启动Flask后端和Tkinter前端GUI分别在两个线程中
    flask_thread = threading.Thread(target=run_flask_server, daemon=True)
    flask_thread.start()

    # 启动Tkinter界面
    run_tkinter_gui()
