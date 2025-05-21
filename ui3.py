import requests
import os
import re
import time
import threading
from googletrans import Translator
import tkinter as tk
from tkinter import Toplevel, simpledialog
from PIL import Image, ImageTk,ImageDraw,ImageFont
from tkinter import ttk, filedialog,messagebox, colorchooser,Button, Canvas, Frame, Scrollbar, Label, Entry, Button, StringVar,Text
from tkinter.ttk import Progressbar
from fontTools.ttLib import TTFont
import shutil
import json
from get_video import replace_prohibited_words
from make_image import *

class VideoGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("视频生成配置")
        self.root.geometry("650x400")
        self.CHINESE_UNICODE_RANGE = (0x4E00, 0x9FFF)
        # 创建主容器：标签页+底部按钮区域
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=50, pady=5)
        # 创建底部按钮区域
        self.create_bottom_controls()
        # 创建各个标签页
        self.create_basic_tab()     # 基本参数标签页
        self.create_font_tab()      # 字体参数标签页
        self.create_text_style_tab()  # 文本样式标签页
        self.tasks_progress = {}  # 用于存储每个任务的进度和进度条
        # 定义文件路径
        self.prohibited_words_file=r".\base\data\prohibited_words.json"
        if os.path.exists(self.prohibited_words_file):
            with open(self.prohibited_words_file, 'r', encoding='utf-8') as file:
                try:
                    self.prohibited_words_dict = json.load(file)
                except:
                    self.prohibited_words_dict = {}
        else:
            self.prohibited_words_dict = {}
        self.create_prohibited_words_tab()
        
        # 存储已下载的抖音视频路径
        self.downloaded_douyin_video = None
        
    def create_static_text_image2(self):
        data = self.select_data()
        
        # 如果是抖音视频，使用已下载的视频
        if data['trans_method'] == "抖音爬取":
            if self.downloaded_douyin_video and os.path.exists(self.downloaded_douyin_video):
                image_path = self.downloaded_douyin_video
            else:
                messagebox.showinfo("提示", "请先下载抖音视频")
                return
        else:
            image_path = self.bg_image_var.get()
            
        ret = self.validate_all_inputs(data)
        data['sentences'] = split_sentences(data['sentences'])
        
        if ret == True:
            chinese_text = data['sentences'][0]
            chinese_text = replace_prohibited_words(chinese_text, self.prohibited_words_file)
            font_path_chinese = './base/font/' + self.font_chinese_var.get()
            chinese_text_size = int(self.chinese_size_var.get())
            chinese_text_color = tuple(self.hex_to_rgb(self.chinese_color_var.get()))
            chinese_text_posotion = float(self.chinese_pos_var.get())
            line_spacing = float(self.line_spacing_var.get())
            cap = cv2.VideoCapture(image_path)
            if not cap.isOpened():
                raise FileNotFoundError(f"无法打开视频文件 {image_path}")
            ret, frame = cap.read()
            if not ret:
                raise ValueError("无法读取视频文件")
            image = create_static_text_image(
                frame,
                chinese_text,
                font_path_chinese,
                chinese_text_size=chinese_text_size,
                chinese_text_color=chinese_text_color,
                chinese_text_posotion=chinese_text_posotion,
                line_spacing=line_spacing,
                )
            pil_img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            
            # 获取原始图片尺寸
            original_width, original_height = pil_img.size
            
            # 获取屏幕尺寸
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            
            # 计算目标尺寸（屏幕的1/4）
            target_width = screen_width // 2
            target_height = screen_height // 2
            
            # 计算保持宽高比的缩放比例
            width_ratio = target_width / original_width
            height_ratio = target_height / original_height
            scale_ratio = min(width_ratio, height_ratio)
            
            # 计算新的尺寸
            new_width = int(original_width * scale_ratio)
            new_height = int(original_height * scale_ratio)
            
            # 缩放图片
            pil_img = pil_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # 创建预览窗口，大小根据缩放后的图片尺寸调整
            preview_window = Toplevel(self.root)
            preview_window.geometry(f"{new_width}x{new_height}")  # 添加一些边距
            preview_window.title("第一帧预览")
            
            # 将生成的图像转换为Tkinter可显示格式
            img_tk = ImageTk.PhotoImage(pil_img)
            preview_label = Label(preview_window, image=img_tk)
            preview_label.image = img_tk  # 保存引用
            preview_label.pack()
        else:
            messagebox.showinfo("输入格式验证失败", ret)
            
    def contains_chinese_characters(self,font_path):
        """检查字体文件是否包含中文字符"""
        try:
            font = TTFont(font_path)
            cmap = font["cmap"]  # 字符映射表

            for table in cmap.tables:
                for codepoint, glyph_name in table.cmap.items():
                    # 判断是否在中文字符的Unicode范围内
                    if self.CHINESE_UNICODE_RANGE[0] <= codepoint <= self.CHINESE_UNICODE_RANGE[1]:
                        return True
            return False
        except Exception as e:
            print(f"无法处理字体文件 {font_path}: {e}")
            return False

    def categorize_fonts_by_language(self,directory):
        """读取文件夹内所有字体文件，并分类为中文字体和英文字体"""
        chinese_fonts = []
        english_fonts = []

        # 遍历文件夹中的所有字体文件
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)

            # 只处理 .ttf 和 .otf 文件
            if os.path.isfile(file_path) and (filename.endswith('.ttf') or filename.endswith('.otf')):
                is_chinese = self.contains_chinese_characters(file_path)
                if is_chinese:
                    chinese_fonts.append(filename)
                else:
                    english_fonts.append(filename)
        return chinese_fonts, english_fonts

    def create_tab_scrollable_frame(self, parent):
        """创建带滚动条的标签页容器"""
        container = Frame(parent)
        # 创建Canvas和滚动条
        canvas = Canvas(container, borderwidth=0)
        scrollbar = Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        # 布局
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        # 创建内部框架
        inner_frame = Frame(canvas)
        canvas.create_window((0, 0), window=inner_frame, anchor="nw")
        # 绑定配置事件
        inner_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        # 绑定鼠标滚轮事件
        canvas.bind("<Enter>", lambda e: self.bind_mousewheel(canvas))
        canvas.bind("<Leave>", lambda e: self.unbind_mousewheel())
        return container, inner_frame

    def bind_mousewheel(self, canvas):
        """绑定指定Canvas的滚轮事件"""
        self.canvas_mousewheel_bind = canvas.bind_all("<MouseWheel>", lambda e: self.on_mouse_wheel(e, canvas))

    def unbind_mousewheel(self):
        """解绑滚轮事件"""
        if hasattr(self, 'canvas_mousewheel_bind'):
            self.root.unbind_all("<MouseWheel>")

    def on_mouse_wheel(self, event, canvas):
        """处理滚轮滚动"""
        if event.delta > 0:
            canvas.yview_scroll(-1, "units")
        else:
            canvas.yview_scroll(1, "units")

    def create_bottom_controls(self):
        """创建底部控制按钮区域"""
        bottom_frame = Frame(self.root)
        bottom_frame.pack(side="bottom", fill="x", pady=10)
        
        # 预览按钮
        self.preview_btn = Button(bottom_frame, text="预览第一帧", command=self.create_static_text_image2)
        self.preview_btn.pack(side="left", padx=20)
        
        # 生成按钮
        self.upload_btn = Button(bottom_frame, text="生成视频", command=self.upload_file)
        self.upload_btn.pack(side="left", padx=20)

    def create_basic_tab(self):
        """创建'基本参数'标签页"""
        tab, inner_frame = self.create_tab_scrollable_frame(self.notebook)
        self.notebook.add(tab, text="基础参数")
        
        # 基础参数组
        self.base_group = self.create_group_frame(inner_frame, "基础参数")
        self.create_transapi_tab()
        self.bg_music_var = self.create_input_row(self.base_group, "背景音乐路径(.mp3/.wav)", "./base/video/bgm.mp3", is_file=True)
        self.bg_msc_volumn_var = self.create_input_row(self.base_group, "背景音乐音量大小", "0.5")
        self.save_path_var = self.create_input_row(self.base_group, "保存路径", "./output", is_dic=True)
        self.proxy_var = self.create_input_row(self.base_group, "代理服务器(可选)\nhttp://ip:port 或 socks5://ip:port", "")
        self.text_var = self.create_input_box(self.base_group, "给女生提供情绪价值的小方法，直男最大的困扰，就是不会提供情绪价值，我今天给你一套万能公式希望你谈恋爱的时候用得上，下面三句话你学会直接情绪价值拉满")

    def create_prohibited_words_tab(self):
        tab, inner_frame = self.create_tab_scrollable_frame(self.notebook)
        self.notebook.add(tab, text="违禁词配置")
        
        left_frame = tk.Frame(inner_frame, width=325, padx=5, pady=5)
        left_frame.pack(side=tk.LEFT, fill=tk.Y)
        # 输入框和标签
        Label(left_frame, text="请输入违禁词：").pack(pady=5)
        self.word_entry = Entry(left_frame, width=30)
        self.word_entry.pack(pady=5)
        Label(left_frame, text="请输入替换词：").pack(pady=5)
        self.replacement_entry = Entry(left_frame, width=30)
        self.replacement_entry.pack(pady=5)
        # 添加按钮
        add_button = tk.Button(left_frame, text="添加违禁词", command=self.add_prohibited_word)
        add_button.pack(pady=10)
        add_button = tk.Button(left_frame, text="删除违禁词", command=self.del_prohibited_word).pack(side="left")
        self.del_prohibited_words = tk.StringVar(value=None)
        self.del_prohibited_entry = Entry(left_frame, textvariable=self.del_prohibited_words,width=30)
        self.del_prohibited_entry.pack(side="left", padx=5)
        # 右侧框架：用于显示违禁词字典
        right_frame = tk.Frame(inner_frame, padx=5, pady=5)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # 显示违禁词的列表框
        tk.Label(right_frame, text="当前违禁词：").pack(pady=5)
        self.prohibited_words_listbox = tk.Listbox(right_frame, width=40, height=14)
        self.prohibited_words_listbox.pack(side="right",pady=5)
        # 初始化时显示当前的违禁词
        self.update_prohibited_words_display()

    def del_prohibited_word(self):
        a=self.prohibited_words_dict.pop(self.del_prohibited_words.get(),None)
        with open(self.prohibited_words_file, 'w', encoding='utf-8') as file:
            json.dump(self.prohibited_words_dict, file, ensure_ascii=False, indent=4)
        self.update_prohibited_words_display()
        self.del_prohibited_entry.delete(0, tk.END)
        
    def add_prohibited_word(self):
        word = self.word_entry.get().strip()
        replacement = self.replacement_entry.get().strip()
        if not word or not replacement:
            messagebox.showwarning("输入错误", "请填写违禁词和替换词。")
            return
        # 添加到字典
        self.prohibited_words_dict[word] = replacement
        # 保存到文件
        with open(self.prohibited_words_file, 'w', encoding='utf-8') as file:
            json.dump(self.prohibited_words_dict, file, ensure_ascii=False, indent=4)
        # 更新界面显示
        self.update_prohibited_words_display()
        # 清空输入框
        self.word_entry.delete(0, tk.END)
        self.replacement_entry.delete(0, tk.END)

    def update_prohibited_words_display(self):
        self.prohibited_words_listbox.delete(0, tk.END)
        for word, replacement in self.prohibited_words_dict.items():
            self.prohibited_words_listbox.insert(tk.END, f"{word} -> {replacement}")

    def update_ttf(self):
        self.cobb1['values']=self.chinese_fonts
        if len(self.chinese_fonts)>0:
            self.cobb1.set(self.font_chinese_var.get())


    def add_ttf(self):
        """点击按钮后选择文件，判断是否为字体文件并分类"""
        file_path = filedialog.askopenfilename(filetypes=[("字体文件", "*.ttf;*.otf")])  # 选择字体文件
        if file_path:  # 如果选择了文件
            if file_path.endswith('.ttf') or file_path.endswith('.otf'):
                # 判断是否为中文字体
                is_chinese = self.contains_chinese_characters(file_path)
                font_name = os.path.basename(file_path)
                try:
                    target_path = os.path.join('./base/font', font_name)  # 构造目标文件路径
                    if not os.path.exists(target_path):
                        shutil.copy(file_path, target_path)  # 复制文件到目标文件夹
                        self.root.after(100, self.update_ttf)
                        if is_chinese:
                            self.chinese_fonts.append(font_name)
                            messagebox.showinfo("成功", f"已添加到中文字体列表: {font_name}")
                        else:
                            messagebox.showinfo("失败", f"{font_name}不是中文字体")
                    else:
                        messagebox.showinfo("警告", f"字体{font_name}已存在")
                except Exception as e:
                    messagebox.showerror("错误", f"文件添加失败: {e}")
            else:
                messagebox.showerror("错误", "请选择有效的字体文件（.ttf 或 .otf）")
    def create_font_tab(self):
        """创建'字体参数'标签页"""
        tab, inner_frame = self.create_tab_scrollable_frame(self.notebook)
        self.notebook.add(tab, text="字体参数")
        # 预览按钮
        self.addttf_btn = Button(inner_frame, text="增加字体", command=self.add_ttf)
        self.chinese_fonts, self.english_fonts = self.categorize_fonts_by_language("./base/font")
        # 创建英文字体下拉选择框
        self.font_chinese_var,self.cobb1 = self.create_combobox(inner_frame, "中文字体", self.chinese_fonts)
        self.cobb1.set(self.chinese_fonts[3])
        self.addttf_btn.pack(side="right", padx=20)

        
    def create_combobox(self, parent, label, choices):
        """创建下拉式选择框"""
        row = Frame(parent)
        row.pack(fill="x", pady=5)
        Label(row, text=label, width=25).pack(side="left")
        var = StringVar(value=choices[0])  # 默认选第一个字体
        combobox = ttk.Combobox(row, textvariable=var, values=choices, state="readonly", width=30)
        combobox.pack(side="left", padx=5)
        return var,combobox

    def create_transapi_tab(self):
        # 语音生成方式
        self.trans_group = self.create_group_frame(self.base_group, "视频输入方式")
        self.trans_method_var = tk.StringVar(value="抖音爬取")

        # 创建选择框
        self.create_radio_button(self.trans_group, "抖音爬取", "抖音爬取", self.trans_method_var)
        self.create_radio_button(self.trans_group, "本地视频上传", "本地视频上传", self.trans_method_var)

        # 显示与选择的 API 相关的配置
        self.transapi_config_frame = tk.Frame(self.trans_group)
        self.transapi_config_frame.pack(fill="both", expand=True)
        self.bg_image_var = self.create_input_row_nopack(self.transapi_config_frame, "背景视频路径", "", is_file=True)
        self.bg_image_var2 = self.create_input_row_nopack(self.transapi_config_frame, "背景视频抖音路径", "")
        # 绑定选择变化事件
        self.trans_method_var.trace_add("write", self.update_transapi_config)
        # 初始化显示
        self.update_transapi_config()

    def update_transapi_config(self, *args):
        """根据选择的语音生成方式更新 API 配置显示"""
        # 清空当前配置
        for widget in self.transapi_config_frame.winfo_children():
            widget.destroy()
        
        # 获取当前选择的语音生成方式
        selected_method = self.trans_method_var.get()

        if selected_method == "抖音爬取":
            url_frame = Frame(self.transapi_config_frame)
            url_frame.pack(fill="x", pady=2)
            Label(url_frame, text="抖音视频网址", width=25).pack(side="left")
            self.bg_image_var2 = tk.StringVar(value=self.bg_image_var2.get() if hasattr(self, 'bg_image_var2') else "")
            entry = Entry(url_frame, textvariable=self.bg_image_var2, width=30)
            entry.pack(side="left", padx=5)
            
            # 添加单独的抖音视频下载按钮
            download_btn = Button(url_frame, text="下载视频", command=self.download_douyin_video)
            download_btn.pack(side="left", padx=5)
            
            # 显示已下载视频的状态
            status_frame = Frame(self.transapi_config_frame)
            status_frame.pack(fill="x", pady=2)
            self.douyin_status_label = Label(status_frame, text="未下载视频", fg="orange")
            self.douyin_status_label.pack(side="left", padx=30)
            
        elif selected_method == "本地视频上传":
            self.bg_image_var = self.create_input_row(self.transapi_config_frame, "本地视频路径", self.bg_image_var.get(), is_file=True)
    
    def download_douyin_video(self):
        """单独下载抖音视频的功能"""
        url = self.bg_image_var2.get()
        if not url or not url.startswith('http'):
            messagebox.showerror("错误", "请输入有效的抖音链接")
            return
            
        # 创建浏览器和代理选择对话框
        browser_window = tk.Toplevel(self.root)
        browser_window.title("下载设置")
        browser_window.geometry("300x400")
        browser_window.resizable(False, False)
        
        # 设置模态窗口
        browser_window.transient(self.root)
        browser_window.grab_set()
        
        # 浏览器选择部分
        Label(browser_window, text="请选择用于下载抖音视频的浏览器:", 
              wraplength=380, justify="center").pack(pady=10)
        
        browser_var = tk.StringVar(value="edge")  # 默认选择Edge
        
        # 创建单选按钮
        browser_frame = Frame(browser_window)
        browser_frame.pack(pady=5)
        
        browsers = [
            ("Edge浏览器", "edge"),
            ("Firefox浏览器", "firefox"),
            ("Chrome浏览器", "chrome")
        ]
        
        for text, value in browsers:
            tk.Radiobutton(browser_frame, text=text, variable=browser_var, value=value).pack(anchor="w", pady=5)
        
        # 代理设置部分
        proxy_frame = Frame(browser_window)
        proxy_frame.pack(pady=5, fill="x", padx=20)
        
        Label(proxy_frame, text="代理设置（如无需代理请留空）:", 
              justify="left", anchor="w").pack(fill="x", pady=5)
        
        proxy_var = tk.StringVar(value="")
        proxy_entry = Entry(proxy_frame, textvariable=proxy_var, width=40)
        proxy_entry.pack(pady=5, fill="x")
        
        Label(proxy_frame, text="代理格式: http://ip:port 或 socks5://ip:port", 
              font=("Arial", 8), fg="gray").pack(fill="x")
        
        # 本地驱动选项
        driver_frame = Frame(browser_window)
        driver_frame.pack(pady=5, fill="x", padx=20)
        
        use_local_driver_var = tk.BooleanVar(value=True)  # 默认使用本地驱动
        use_local_driver_cb = tk.Checkbutton(
            driver_frame, 
            text="使用本地驱动（推荐，避免下载卡住）", 
            variable=use_local_driver_var
        )
        use_local_driver_cb.pack(anchor="w", pady=5)
        
        Label(driver_frame, text="本地驱动路径: ./drivers/", 
              font=("Arial", 8), fg="gray").pack(anchor="w")
        
        # 确认和取消按钮
        btn_frame = Frame(browser_window)
        btn_frame.pack(pady=15)
        
        def on_confirm():
            selected_browser = browser_var.get()
            proxy = proxy_var.get().strip()
            use_local_driver = use_local_driver_var.get()
            browser_window.destroy()
            self.start_douyin_download(url, selected_browser, proxy, use_local_driver)
            
        def on_cancel():
            browser_window.destroy()
            
        Button(btn_frame, text="确认", width=10, command=on_confirm).pack(side="left", padx=10)
        Button(btn_frame, text="取消", width=10, command=on_cancel).pack(side="left", padx=10)
        
        # 等待用户操作
        self.root.wait_window(browser_window)
    
    def start_douyin_download(self, url, browser_type, proxy=None, use_local_driver=False):
        """开始下载抖音视频"""
        # 创建下载窗口
        download_window = tk.Toplevel(self.root)
        download_window.title("正在下载抖音视频")
        download_window.geometry("400x150")
        download_window.resizable(False, False)
        
        # 显示URL和浏览器信息
        browser_name = {"edge": "Edge", "firefox": "Firefox", "chrome": "Chrome"}[browser_type]
        proxy_info = f"，使用代理: {proxy}" if proxy else ""
        local_driver_info = "，使用本地驱动" if use_local_driver else ""
        Label(download_window, text=f"正在使用{browser_name}浏览器下载抖音视频{proxy_info}{local_driver_info}:\n{url}", 
              wraplength=380, justify="center").pack(pady=5)
        
        # 创建进度条
        style = ttk.Style()
        style.configure("Douyin.Horizontal.TProgressbar", background='#ff0050')  # 抖音红色进度条
        progress_bar = ttk.Progressbar(
            download_window, 
            length=350, 
            mode="indeterminate",
            style="Douyin.Horizontal.TProgressbar"
        )
        progress_bar.pack(pady=5)
        progress_bar.start(15)  # 启动动画
        
        # 状态标签
        status_label = Label(download_window, text="正在下载中...", fg="blue")
        status_label.pack(pady=5)
        
        # 保存位置标签
        save_path_label = Label(download_window, text="", wraplength=380)
        save_path_label.pack(pady=5)
        
        # 添加关闭按钮
        def close_download_window():
            download_window.destroy()
            
        close_button = Button(download_window, text="关闭", command=close_download_window)
        close_button.pack(pady=5)
        
        download_window.update()
        
        # 启动下载线程
        def do_download():
            try:
                # 构建请求数据
                download_data = {
                    'trans_method': "抖音爬取",
                    'backGround_image_path2': url,
                    'browser_type': browser_type,  # 添加浏览器类型参数
                    'ffmpeg_path': "./ffmpeg/bin/ffmpeg.exe",
                    'use_local_driver': use_local_driver  # 添加是否使用本地驱动参数
                }
                
                # 如果有代理设置，添加到请求数据中
                if proxy:
                    download_data['proxy'] = proxy
                
                # 发送请求
                response = requests.post('http://127.0.0.1:5000/download_douyin', json=download_data)
                
                # 处理响应
                def handle_response():
                    if not download_window.winfo_exists():
                        return
                        
                    if response.status_code == 200:
                        result = response.json()
                        video_path = result.get('video_path')
                        
                        if video_path and os.path.exists(video_path):
                            # 更新UI
                            progress_bar.stop()
                            progress_bar.configure(mode="determinate")
                            progress_bar["value"] = 100
                            status_label.config(text="下载完成！")
                            save_path_label.config(text=f"保存位置: {os.path.abspath(video_path)}", fg="green")
                            
                            # 保存路径并更新主界面
                            self.downloaded_douyin_video = video_path
                            self.douyin_status_label.config(text=f"已下载到: {os.path.abspath(video_path)}", fg="green")
                            
                            # 显示成功消息
                            messagebox.showinfo("成功", "抖音视频下载成功！下载位置："+os.path.abspath(video_path))
                            close_download_window()
                        else:
                            messagebox.showerror("错误", "下载成功但找不到视频文件")
                            close_download_window()
                            
                    else:
                        err = "下载失败，请检查链接或网络连接"
                        try:
                            err = response.json().get('error', err)
                        except:
                            pass
                        messagebox.showerror("下载失败", err)
                        close_download_window()
                
                # 在主线程中处理UI更新
                self.root.after(0, handle_response)
                
            except Exception as e:
                def show_error():
                    if download_window.winfo_exists():
                        messagebox.showerror("错误", f"下载失败: {str(e)}")
                        close_download_window()
                self.root.after(0, show_error)
        
        threading.Thread(target=do_download, daemon=True).start()

    def create_text_style_tab(self):
        """创建'文本样式'标签页"""
        tab, inner_frame = self.create_tab_scrollable_frame(self.notebook)
        self.notebook.add(tab, text="文本样式")
        
        # 文本样式组
        self.text_style_group = self.create_group_frame(inner_frame, "文本样式")
        self.chinese_size_var = self.create_input_row(self.text_style_group, "中文文字大小", "10")
        self.chinese_color_var = self.create_input_row(self.text_style_group, "中文文字颜色", "#ffffff", is_color=True)
        self.chinese_pos_var = self.create_input_row(self.text_style_group, "内容文字位置\n(越大内容越靠近上边框)", "1.2")
        self.line_spacing_var = self.create_input_row(self.text_style_group, "行间距", "0.8")

    # 创建分组框架
    def create_group_frame(self, parent, title):
        frame = Frame(parent, bd=2, relief="groove", padx=5, pady=5)
        Label(frame, text=title, font=('Arial', 10, 'bold')).pack(anchor="w")
        frame.pack(fill="x", padx=10, pady=5)  # 让frame显示出来并加一些间距
        return frame

    def create_radio_button(self, frame, text, value, var):
        rb = tk.Radiobutton(frame, text=text, variable=var, value=value)
        rb.pack(anchor="w")
        
    # 通用输入组件生成函数
    def create_input_row(self, frame, label, default=None, is_color=False, is_file=False,is_dic=False):
        row = Frame(frame)
        row.pack(fill="x", pady=2)
        Label(row, text=label, width=25).pack(side="left")
        var = tk.StringVar(value=default)
        if is_color:
            Button(row, text="选择颜色", command=lambda: self.choose_color(var)).pack(side="left")
        elif is_file:
            Button(row, text="浏览文件", command=lambda: self.choose_file(var)).pack(side="left")
        elif is_dic:
            Button(row, text="选择保存路径", command=lambda: self.select_save_path(var)).pack(side="left")
        entry = Entry(row, textvariable=var,width=30)
        entry.pack(side="left", padx=5)
        return var

    def create_input_box(self, frame,default=None):
        row = Frame(frame)
        row.pack(fill="x", pady=2)
        input_textbox =Text(row, height=13, width=65)
        input_textbox.delete("1.0", tk.END)
        input_textbox.insert(tk.END, default)
        input_textbox.pack()
        return input_textbox
    
    def create_input_row_nopack(self, frame, label, default=None, is_color=False, is_file=False,is_dic=False):
        row = Frame(frame)
        row.pack(fill="x", pady=2)
        Label(row, text=label, width=25).pack(side="left")
        var = tk.StringVar(value=default)
        if is_color:
            Button(row, text="选择颜色", command=lambda: self.choose_color(var)).pack(side="left")
        elif is_file:
            Button(row, text="浏览文件", command=lambda: self.choose_file(var)).pack(side="left")
        elif is_dic:
            Button(row, text="选择保存路径", command=lambda: self.select_save_path(var)).pack(side="left")
        return var

    # 颜色选择器和文件选择器
    def choose_color(self, var):
        color = colorchooser.askcolor()[1]
        if color:
            var.set(color)

    def choose_file(self, var):
        path = filedialog.askopenfilename()
        if path:
            var.set(path)

    def select_save_path(self,var):
        folder_path = filedialog.askdirectory()  # 选择文件夹
        if folder_path:
            var.set(folder_path)

    def select_data(self):
        data = {
            'sentences': self.text_var.get("1.0", tk.END),
            'trans_method': self.trans_method_var.get(),
            'backGround_image_path': self.bg_image_var.get(),
            'backGround_image_path2': self.bg_image_var2.get(),
            'bgm': self.bg_music_var.get(),
            'save_path': self.save_path_var.get(),
            'ffmpeg_path': "./ffmpeg/bin/ffmpeg.exe",
            'font_path_chinese': './base/font/' + self.font_chinese_var.get(),
            'chinese_text_size': self.chinese_size_var.get(),
            'chinese_text_color': self.chinese_color_var.get(),
            'chinese_text_position': self.chinese_pos_var.get(),
            'line_spacing': self.line_spacing_var.get(),
            'bgm_volumn': self.bg_msc_volumn_var.get(),
            'proxy': self.proxy_var.get().strip() if hasattr(self, 'proxy_var') else "",
            'use_local_driver': True  # 默认使用本地驱动，避免下载卡住
        }
        return data
    # 上传函数
    def upload_file(self):
        # 收集所有参数
        data = self.select_data()
        print(data)
        ret = self.validate_all_inputs(data)
        data['sentences'] = split_sentences(data['sentences'])
        data['chinese_text_color'] = self.hex_to_rgb(self.chinese_color_var.get())
        
        # 如果是抖音视频，检查是否已下载
        if data['trans_method'] == "抖音爬取":
            if self.downloaded_douyin_video and os.path.exists(self.downloaded_douyin_video):
                # 使用已下载的视频路径替换网址
                data['trans_method'] = "本地视频上传"  # 修改为本地模式
                data['backGround_image_path'] = self.downloaded_douyin_video
                data['backGround_image_path2'] = ""  # 清空URL
            else:
                messagebox.showinfo("提示", "请先下载抖音视频")
                return
        
        if not os.path.exists(self.prohibited_words_file):
            messagebox.showinfo("失败", f'未在{self.prohibited_words_file}找到违禁字列表')
            return
            
        if ret == True:
            print("所有输入格式验证通过")
            try:
                # 发送请求到后端
                response = requests.post('http://127.0.0.1:5000/upload', json=data)
                
                if response.status_code == 200:
                    task_id = response.json().get('task_id')
                    
                    # 创建进度条窗口
                    self.make_progress_bar(task_id)
                    messagebox.showinfo("成功", "视频生成已开始！")
                else:
                    # 处理错误响应
                    try:
                        error_data = response.json()
                        error_message = error_data.get('error', f"服务器错误: {response.status_code}")
                    except:
                        error_message = f"服务器错误: {response.text if response.text else response.status_code}"
                    
                    messagebox.showerror("错误", error_message)
            except Exception as e:
                messagebox.showerror("错误", f"连接失败: {str(e)}")
        else:
            messagebox.showinfo("输入格式验证失败", ret)
        

    def make_progress_bar(self, task_id):
        """生成视频时，显示生成进度"""
        # 创建弹窗显示进度
        progress_window = tk.Toplevel(self.root)
        progress_window.title(f"任务ID: {task_id}")
        progress_window.geometry("400x150")
        
        # 创建进度条样式
        style = ttk.Style()
        style.configure("Regular.Horizontal.TProgressbar", background='#0078d7')  # 蓝色进度条
        style.configure("Error.Horizontal.TProgressbar", background='red')  # 红色错误进度条
        
        # 添加进度条
        progress_bar = ttk.Progressbar(
            progress_window, 
            length=380, 
            mode="determinate", 
            maximum=100,
            style="Regular.Horizontal.TProgressbar"
        )
        progress_bar.pack(pady=10)
        
        # 进度文本标签
        progress_label = Label(progress_window, text="正在准备...")
        progress_label.pack(pady=5)
        
        # 添加错误信息显示区域
        error_label = Label(progress_window, text="", fg="blue", wraplength=380, justify="left")
        error_label.pack(pady=5, fill="x")
        
        # 添加关闭按钮
        close_btn = Button(progress_window, text="关闭", command=progress_window.destroy)
        close_btn.pack(pady=5)
        
        # 存储任务的进度和控件，便于后续更新
        self.tasks_progress[task_id] = {
            'progress_bar': progress_bar,
            'progress_label': progress_label,
            'error_label': error_label,
            'window': progress_window,
            'is_indeterminate': False  # 跟踪当前进度条模式
        }
        
        self.update_progress(task_id)
    
    def update_progress(self, task_id):
        """定期更新任务进度"""
        try:
            if task_id not in self.tasks_progress:
                return  # 任务已不存在
                
            response = requests.get(f'http://127.0.0.1:5000/progress/{task_id}')
            if not response.ok:
                self.root.after(0, lambda: self.update_ui(task_id, -1, f"服务器响应错误: {response.status_code}"))
                return
                
            data = response.json()
            current_progress = data.get('progress', 0)
            error_message = data.get('error')
            
            # 处理抖音下载状态 - 检测特殊状态信息
            if error_message and "正在从抖音获取视频" in error_message:
                self.root.after(0, lambda: self.set_indeterminate_mode(task_id, error_message))
                self.root.after(300, lambda: self.update_progress(task_id))  # 更快地更新
                return
                
            # 如果不是特殊状态，确保进度条是确定模式
            self.root.after(0, lambda: self.set_determinate_mode(task_id))
            
            # 处理错误或完成状态
            if current_progress == -1:  # 错误状态
                self.root.after(0, lambda: self.show_error(task_id, error_message))
                return  # 停止更新
            elif current_progress >= 100:  # 完成状态
                self.root.after(0, lambda: self.update_ui(task_id, 100, None))
                self.root.after(1000, lambda: messagebox.showinfo("完成", "视频生成完成！"))
                self.root.after(1500, lambda: self.tasks_progress[task_id]['window'].destroy())
                return  # 停止更新
                
            # 普通进度更新
            self.root.after(0, lambda: self.update_ui(task_id, current_progress, error_message))
            
            # 继续更新，标准间隔
            self.root.after(500, lambda: self.update_progress(task_id))
                
        except Exception as e:
            if task_id in self.tasks_progress:  # 确保任务存在
                self.root.after(0, lambda: self.update_ui(task_id, -1, f"连接服务器失败: {str(e)}"))
    
    def set_indeterminate_mode(self, task_id, status_message=None):
        """设置进度条为不确定模式（动画模式）"""
        if task_id not in self.tasks_progress:
            return
            
        task = self.tasks_progress[task_id]
        if not task.get('is_indeterminate'):  # 只在需要时切换模式
            progress_bar = task['progress_bar']
            if progress_bar.winfo_exists():  # 确保控件存在
                # 清除当前状态并切换模式
                progress_bar.stop()
                progress_bar['value'] = 0
                progress_bar.configure(mode='indeterminate')
                progress_bar.start(15)  # 启动动画
                
                # 更新标签
                task['progress_label'].config(text="正在下载抖音视频...")
                task['is_indeterminate'] = True
                
                # 如果提供了状态消息，显示它
                if status_message:
                    task['error_label'].config(text=status_message, fg="blue")
    
    def set_determinate_mode(self, task_id):
        """设置进度条为确定模式（固定进度模式）"""
        if task_id not in self.tasks_progress:
            return
            
        task = self.tasks_progress[task_id]
        if task.get('is_indeterminate'):  # 只在需要时切换模式
            progress_bar = task['progress_bar']
            if progress_bar.winfo_exists():  # 确保控件存在
                # 停止动画并切换模式
                progress_bar.stop()
                progress_bar.configure(mode='determinate')
                task['is_indeterminate'] = False
    
    def show_error(self, task_id, error_message):
        """显示错误状态"""
        if task_id not in self.tasks_progress:
            return
            
        task = self.tasks_progress[task_id]
        progress_bar = task['progress_bar']
        
        # 确保是确定模式
        if task.get('is_indeterminate'):
            progress_bar.stop()
            progress_bar.configure(mode='determinate')
            task['is_indeterminate'] = False
        
        # 设置红色错误样式
        progress_bar.configure(style="Error.Horizontal.TProgressbar")
        progress_bar['value'] = 100
        
        # 更新标签
        task['progress_label'].config(text="处理失败")
        if error_message:
            task['error_label'].config(text=f"错误: {error_message}", fg="red")

    def update_ui(self, task_id, value, error_message=None):
        """更新普通进度UI"""
        if task_id not in self.tasks_progress:
            return
            
        task = self.tasks_progress[task_id]
        progress_bar = task['progress_bar']
        
        # 确保不是动画模式
        if task.get('is_indeterminate'):
            self.set_determinate_mode(task_id)
        
        # 更新进度
        value = min(max(int(value), 0), 100)  # 确保值在0-100范围
        progress_bar['value'] = value
        
        # 更新标签
        task['progress_label'].config(text=f"生成进度: {value}%")
        
        # 更新可能的警告信息
        if error_message:
            task['error_label'].config(text=f"警告: {error_message}", fg="orange")
        else:
            task['error_label'].config(text="", fg="black")

    # RGB转换函数
    def hex_to_rgb(self, hex_color):
        try:
            hex_color = hex_color.lstrip('#')
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        except ValueError:
            return False

    def validate_all_inputs(self,data):
        if not validate_input(data['sentences'], 'non_empty_text'):
            return "文本内容不能为空或只包含空格！"
        if data['trans_method']=="抖音爬取":
            if not validate_input(data['backGround_image_path2'], 'net_url'):
                return "背景视频抖音路径无效！"
        else:
            if not validate_input(data['backGround_image_path'], 'file_path'):
                return "背景视频路径无效！"
        if not validate_input(data['bgm'], 'file_path'):
            return "背景音乐路径无效！"
        if not validate_input(data['bgm_volumn'], 'number'):
            return "背景音乐音量无效！"
        if not validate_input(data['save_path'], 'directory_path'):
            return "保存路径无效！"
        if not validate_input(data['ffmpeg_path'], 'file_path'):
            return "FFmpeg路径无效！"
        if not validate_input(data['font_path_chinese'], 'file_path'):
            return "中文字体路径无效！"
        if not validate_input(data['chinese_text_size'], 'number'):
            return "中文文字大小无效！"
        if not validate_input(data['chinese_text_color'], 'hex_color'):
            return "中文文字颜色无效！"
        if not validate_input(data['chinese_text_position'], 'number'):
            return "中文文字位置格式不正确！"
        if not validate_input(data['line_spacing'], 'number'):
            return "行间距无效！"
        # 如果所有验证通过
        return True
def validate_input(value, validation_type):
    if validation_type == 'non_empty_text':
        if not value or value.isspace():
            return False
        return True
    elif validation_type == 'net_url':
        if not value or not value.startswith('http'):
            return False
        return True
    elif validation_type == 'file_path':
        if not os.path.isfile(value):
            return False
        return True
    elif validation_type == 'directory_path':
        if not os.path.isdir(value):
            return False
        return True
    elif validation_type == 'hex_color':
        try:
            hex_color = value.lstrip('#')
            tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        except ValueError:
            return False
        return True
    elif validation_type == 'number':
        try:
            float(value)
            return True
        except ValueError:
            return False
    elif validation_type == 'coordinates':
        try:
            coords = value.split(',')
            if len(coords) != 2:
                return False
            x, y = float(coords[0]), float(coords[1])
            return True
        except ValueError:
            return False
    return False

def split_sentences(text):
    """分句函数，处理中英文标点和换行符，保护括号、引号和注释中的内容"""
    # 处理换行符
    text = re.sub(r'\n\s*\n', '\n', text)
    
    # 按段落分割
    paragraphs = text.split('\n')
    all_sentences = []
    
    # 定义所有可能的开始和结束符号对
    pairs = {
        '"': '"',  # 英文双引号
        '“': '”',  # 中文双引号
        "'": "'",  # 英文单引号
        "‘":"’",
        '(': ')',  # 英文括号
        '（': '）',  # 中文括号
        '[': ']',  # 英文方括号
        '【': '】'  # 中文方括号
    }
    
    # 定义句子结束的标点符号
    sentence_enders = {'。', '？', '！', '.', '?', '!', '；', ';', '，', ',', '：', ':'}
    
    for paragraph in paragraphs:
        if not paragraph.strip():
            continue
        
        # 初始化变量
        current_sentence = []
        stack = []  # 用于跟踪符号对
        i = 0
        
        while i < len(paragraph):
            char = paragraph[i]
            current_sentence.append(char)
            # 处理符号对
            if char in pairs:
                stack.append(char)
            elif stack and char == pairs[stack[-1]]:
                stack.pop()
            # 只有在不在任何符号对内时才考虑分割
            if not stack and char in sentence_enders:
                sentence = ''.join(current_sentence).strip()
                if sentence:
                    all_sentences.append(sentence)
                current_sentence = []
            
            i += 1
        
        # 处理段落末尾的剩余内容
        if current_sentence:
            sentence = ''.join(current_sentence).strip()
            if sentence:
                all_sentences.append(sentence)
        # 处理每个句子末尾的标点符号
        for i in range(len(all_sentences)):
            if all_sentences[i][-1] in sentence_enders:
                all_sentences[i] = all_sentences[i][0:-1]
    return all_sentences

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoGeneratorApp(root)
    root.mainloop()
