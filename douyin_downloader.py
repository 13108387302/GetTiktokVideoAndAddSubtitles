import requests
import re
import os
import time
import hashlib
import logging
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor
import json
import traceback
from urllib.parse import quote
from datetime import datetime
import shutil

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('douyin_downloader')

# 尝试导入Selenium相关库
SELENIUM_AVAILABLE = False
EDGE_AVAILABLE = False
FIREFOX_AVAILABLE = False
CHROME_AVAILABLE = False

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
    
    # 检查各浏览器驱动可用性
    try:
        from selenium.webdriver.edge.options import Options as EdgeOptions
        from selenium.webdriver.edge.service import Service as EdgeService
        from webdriver_manager.microsoft import EdgeChromiumDriverManager
        EDGE_AVAILABLE = True
    except ImportError:
        pass
        
    try:
        from selenium.webdriver.firefox.options import Options as FirefoxOptions
        from selenium.webdriver.firefox.service import Service as FirefoxService
        from webdriver_manager.firefox import GeckoDriverManager
        FIREFOX_AVAILABLE = True
    except ImportError:
        pass
        
    try:
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        from selenium.webdriver.chrome.service import Service as ChromeService
        from webdriver_manager.chrome import ChromeDriverManager
        CHROME_AVAILABLE = True
    except ImportError:
        pass
except ImportError:
    pass

# 定义本地默认驱动路径
DEFAULT_DRIVER_PATHS = {
    "edge": "./drivers/msedgedriver.exe",
    "firefox": "./drivers/geckodriver.exe", 
    "chrome": "./drivers/chromedriver.exe"
}

class DouyinDownloader:
    def __init__(self, save_path="./download_videos", browser_type="edge", driver_path=None, proxy=None, use_local_driver=False):
        """初始化抖音下载器
        
        参数:
            save_path: 视频保存路径
            browser_type: 浏览器类型，可选值为"edge", "firefox", "chrome"
            driver_path: 驱动路径，如果不指定则自动使用webdriver_manager下载
            proxy: HTTP代理地址，格式为"http://ip:port"或"socks5://ip:port"
            use_local_driver: 是否使用本地驱动而不是自动下载
        """
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
            'Referer': 'https://www.douyin.com/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Cookie': 'msToken='+hashlib.md5(str(time.time()).encode()).hexdigest(),
        }
        self.save_path = save_path
        self.browser_type = browser_type.lower()
        self.driver_path = driver_path
        self.proxy = proxy  # 保存代理地址
        self.use_local_driver = use_local_driver  # 是否使用本地驱动
        self.driver = None
        self.success_count = 0
        self.fail_count = 0
        
        # 验证浏览器类型可用性
        self.use_selenium = False
        if SELENIUM_AVAILABLE:
            if self.browser_type == "edge" and EDGE_AVAILABLE:
                self.use_selenium = True
            elif self.browser_type == "firefox" and FIREFOX_AVAILABLE:
                self.use_selenium = True
            elif self.browser_type == "chrome" and CHROME_AVAILABLE:
                self.use_selenium = True
            else:
                # 如果指定的浏览器不可用，尝试使用其他可用的浏览器
                if EDGE_AVAILABLE:
                    self.browser_type = "edge"
                    self.use_selenium = True
                    logger.info("指定的浏览器不可用，将使用Edge浏览器")
                elif FIREFOX_AVAILABLE:
                    self.browser_type = "firefox"
                    self.use_selenium = True
                    logger.info("指定的浏览器不可用，将使用Firefox浏览器")
                elif CHROME_AVAILABLE:
                    self.browser_type = "chrome"
                    self.use_selenium = True
                    logger.info("指定的浏览器不可用，将使用Chrome浏览器")
        
        # 创建保存目录
        os.makedirs(save_path, exist_ok=True)
        
        # 如果使用本地驱动，确保drivers目录存在
        if self.use_local_driver:
            os.makedirs("./drivers", exist_ok=True)
        
        # 初始化Selenium(如果启用)
        if self.use_selenium:
            self._init_selenium()
    
    def _init_selenium(self):
        """初始化Selenium WebDriver"""
        try:
            # 初始化不同类型的浏览器
            if self.browser_type == "edge":
                self._init_edge()
            elif self.browser_type == "firefox":
                self._init_firefox()
            elif self.browser_type == "chrome":
                self._init_chrome()
            else:
                logger.error(f"不支持的浏览器类型: {self.browser_type}")
                self.use_selenium = False
                return
                
            # 设置通用配置
            if self.driver:
                self.driver.set_page_load_timeout(30)
                # 隐藏自动化特征
                if self.browser_type != "firefox":  # Firefox不支持此脚本
                    self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
                logger.info(f"已成功初始化 {self.browser_type.title()} 浏览器")
        except Exception as e:
            logger.error(f"初始化浏览器失败: {e}")
            self.use_selenium = False
            
    def _init_edge(self):
        """初始化Edge浏览器"""
        options = EdgeOptions()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument(f'user-agent={self.headers["User-Agent"]}')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument("--disable-extensions")
        options.add_argument("--lang=zh-CN")
        
        # 添加代理设置
        if self.proxy:
            if self.proxy.startswith("socks5://"):  # SOCKS5代理
                logger.info(f"使用SOCKS5代理: {self.proxy}")
                options.add_argument(f'--proxy-server={self.proxy}')
            elif self.proxy.startswith("http://"):  # HTTP代理
                logger.info(f"使用HTTP代理: {self.proxy}")
                options.add_argument(f'--proxy-server={self.proxy}')
        
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        try:
            if self.driver_path:
                # 使用指定驱动路径
                logger.info(f"使用指定的Edge驱动: {self.driver_path}")
                service = EdgeService(executable_path=self.driver_path)
                self.driver = webdriver.Edge(service=service, options=options)
            elif self.use_local_driver:
                # 使用本地默认驱动
                default_path = DEFAULT_DRIVER_PATHS["edge"]
                if os.path.exists(default_path):
                    logger.info(f"使用本地Edge驱动: {default_path}")
                    service = EdgeService(executable_path=default_path)
                    self.driver = webdriver.Edge(service=service, options=options)
                else:
                    logger.warning(f"本地Edge驱动不存在: {default_path}，将尝试自动下载")
                    # 尝试创建驱动目录
                    os.makedirs(os.path.dirname(default_path), exist_ok=True)
                    # 自动下载并保存到指定位置
                    try:
                        logger.info("开始下载Edge驱动...")
                        driver_path = EdgeChromiumDriverManager().install()
                        # 复制到默认路径
                        if os.path.exists(driver_path):
                            shutil.copy(driver_path, default_path)
                            logger.info(f"Edge驱动下载成功并复制到: {default_path}")
                        service = EdgeService(executable_path=default_path if os.path.exists(default_path) else driver_path)
                        self.driver = webdriver.Edge(service=service, options=options)
                    except Exception as e:
                        logger.error(f"自动下载Edge驱动失败: {e}")
                        raise
            else:
                # 自动下载驱动
                logger.info("开始自动下载Edge驱动...")
                try:
                    service = EdgeService(EdgeChromiumDriverManager().install())
                    self.driver = webdriver.Edge(service=service, options=options)
                    logger.info("Edge驱动下载安装成功")
                except Exception as e:
                    logger.error(f"自动下载Edge驱动失败: {e}")
                    # 如果自动下载失败，尝试使用本地驱动
                    default_path = DEFAULT_DRIVER_PATHS["edge"]
                    if os.path.exists(default_path):
                        logger.info(f"使用本地Edge驱动: {default_path}")
                        service = EdgeService(executable_path=default_path)
                        self.driver = webdriver.Edge(service=service, options=options)
                    else:
                        raise
        except Exception as e:
            logger.error(f"Edge浏览器初始化失败: {e}")
            raise
            
    def _init_firefox(self):
        """初始化Firefox浏览器"""
        options = FirefoxOptions()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.set_preference("general.useragent.override", self.headers["User-Agent"])
        options.set_preference("intl.accept_languages", "zh-CN,zh")
        
        # 添加代理设置
        if self.proxy:
            # 解析代理地址
            proxy_parts = self.proxy.split("://")
            if len(proxy_parts) == 2:
                proxy_type, proxy_address = proxy_parts
                host, port = proxy_address.split(":")
                
                if proxy_type == "http":
                    logger.info(f"使用HTTP代理: {self.proxy}")
                    options.set_preference("network.proxy.type", 1)
                    options.set_preference("network.proxy.http", host)
                    options.set_preference("network.proxy.http_port", int(port))
                    options.set_preference("network.proxy.ssl", host)
                    options.set_preference("network.proxy.ssl_port", int(port))
                elif proxy_type == "socks5":
                    logger.info(f"使用SOCKS5代理: {self.proxy}")
                    options.set_preference("network.proxy.type", 1)
                    options.set_preference("network.proxy.socks", host)
                    options.set_preference("network.proxy.socks_port", int(port))
                    options.set_preference("network.proxy.socks_version", 5)
        
        try:
            if self.driver_path:
                # 使用指定驱动路径
                logger.info(f"使用指定的Firefox驱动: {self.driver_path}")
                service = FirefoxService(executable_path=self.driver_path)
                self.driver = webdriver.Firefox(service=service, options=options)
            elif self.use_local_driver:
                # 使用本地默认驱动
                default_path = DEFAULT_DRIVER_PATHS["firefox"]
                if os.path.exists(default_path):
                    logger.info(f"使用本地Firefox驱动: {default_path}")
                    service = FirefoxService(executable_path=default_path)
                    self.driver = webdriver.Firefox(service=service, options=options)
                else:
                    logger.warning(f"本地Firefox驱动不存在: {default_path}，将尝试自动下载")
                    # 尝试创建驱动目录
                    os.makedirs(os.path.dirname(default_path), exist_ok=True)
                    # 自动下载并保存到指定位置
                    try:
                        logger.info("开始下载Firefox驱动...")
                        driver_path = GeckoDriverManager().install()
                        # 复制到默认路径
                        if os.path.exists(driver_path):
                            shutil.copy(driver_path, default_path)
                            logger.info(f"Firefox驱动下载成功并复制到: {default_path}")
                        service = FirefoxService(executable_path=default_path if os.path.exists(default_path) else driver_path)
                        self.driver = webdriver.Firefox(service=service, options=options)
                    except Exception as e:
                        logger.error(f"自动下载Firefox驱动失败: {e}")
                        raise
            else:
                # 自动下载驱动
                logger.info("开始自动下载Firefox驱动...")
                try:
                    service = FirefoxService(GeckoDriverManager().install())
                    self.driver = webdriver.Firefox(service=service, options=options)
                    logger.info("Firefox驱动下载安装成功")
                except Exception as e:
                    logger.error(f"自动下载Firefox驱动失败: {e}")
                    # 如果自动下载失败，尝试使用本地驱动
                    default_path = DEFAULT_DRIVER_PATHS["firefox"]
                    if os.path.exists(default_path):
                        logger.info(f"使用本地Firefox驱动: {default_path}")
                        service = FirefoxService(executable_path=default_path)
                        self.driver = webdriver.Firefox(service=service, options=options)
                    else:
                        raise
        except Exception as e:
            logger.error(f"Firefox浏览器初始化失败: {e}")
            raise
            
    def _init_chrome(self):
        """初始化Chrome浏览器"""
        options = ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument(f'user-agent={self.headers["User-Agent"]}')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument("--disable-extensions")
        options.add_argument("--lang=zh-CN")
        
        # 添加代理设置
        if self.proxy:
            if self.proxy.startswith("socks5://") or self.proxy.startswith("http://"):
                logger.info(f"使用代理: {self.proxy}")
                options.add_argument(f'--proxy-server={self.proxy}')
        
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        try:
            if self.driver_path:
                # 使用指定驱动路径
                logger.info(f"使用指定的Chrome驱动: {self.driver_path}")
                service = ChromeService(executable_path=self.driver_path)
                self.driver = webdriver.Chrome(service=service, options=options)
            elif self.use_local_driver:
                # 使用本地默认驱动
                default_path = DEFAULT_DRIVER_PATHS["chrome"]
                if os.path.exists(default_path):
                    logger.info(f"使用本地Chrome驱动: {default_path}")
                    service = ChromeService(executable_path=default_path)
                    self.driver = webdriver.Chrome(service=service, options=options)
                else:
                    logger.warning(f"本地Chrome驱动不存在: {default_path}，将尝试自动下载")
                    # 尝试创建驱动目录
                    os.makedirs(os.path.dirname(default_path), exist_ok=True)
                    # 自动下载并保存到指定位置
                    try:
                        logger.info("开始下载Chrome驱动...")
                        driver_path = ChromeDriverManager().install()
                        # 复制到默认路径
                        if os.path.exists(driver_path):
                            shutil.copy(driver_path, default_path)
                            logger.info(f"Chrome驱动下载成功并复制到: {default_path}")
                        service = ChromeService(executable_path=default_path if os.path.exists(default_path) else driver_path)
                        self.driver = webdriver.Chrome(service=service, options=options)
                    except Exception as e:
                        logger.error(f"自动下载Chrome驱动失败: {e}")
                        raise
            else:
                # 自动下载驱动
                logger.info("开始自动下载Chrome驱动...")
                try:
                    service = ChromeService(ChromeDriverManager().install())
                    self.driver = webdriver.Chrome(service=service, options=options)
                    logger.info("Chrome驱动下载安装成功")
                except Exception as e:
                    logger.error(f"自动下载Chrome驱动失败: {e}")
                    # 如果自动下载失败，尝试使用本地驱动
                    default_path = DEFAULT_DRIVER_PATHS["chrome"]
                    if os.path.exists(default_path):
                        logger.info(f"使用本地Chrome驱动: {default_path}")
                        service = ChromeService(executable_path=default_path)
                        self.driver = webdriver.Chrome(service=service, options=options)
                    else:
                        raise
        except Exception as e:
            logger.error(f"Chrome浏览器初始化失败: {e}")
            raise
    
    def __del__(self):
        """析构函数，确保关闭WebDriver"""
        if hasattr(self, 'driver') and self.driver:
            try:
                self.driver.quit()
            except:
                pass
            
    def extract_video_id(self, url):
        """从抖音分享链接中提取视频ID"""
        # 处理短链接
        if 'v.douyin.com' in url or 'www.iesdouyin.com' in url:
            try:
                # 如果有代理，使用代理发送请求
                if self.proxy:
                    proxies = {
                        'http': self.proxy,
                        'https': self.proxy
                    }
                    response = requests.head(url, headers=self.headers, allow_redirects=True, proxies=proxies)
                else:
                    response = requests.head(url, headers=self.headers, allow_redirects=True)
                url = response.url
            except:
                return None
        
        # 从URL中提取视频ID
        try:
            # 尝试从URL路径中提取
            match = re.search(r'/video/(\d+)', url)
            if match:
                return match.group(1)
            
            # 从查询参数中提取
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            
            for param in ['item_id', 'video_id', 'id']:
                if param in query_params:
                    return query_params[param][0]
            
            return None
        except:
            return None
    
    def _get_video_info_via_selenium(self, url):
        """使用Selenium从网页获取视频信息"""
        if not self.driver:
            return None
            
        try:
            logger.info(f"正在使用{self.browser_type}浏览器访问抖音页面")
            self.driver.get(url)
            time.sleep(5)
            
            # 尝试通过滚动页面来触发视频加载
            self.driver.execute_script("window.scrollBy(0, 300);")
            time.sleep(1)
            
            # 获取页面源码
            page_source = self.driver.page_source
            
            # 保存源码用于调试
            with open("douyin_page_source.html", "w", encoding="utf-8") as f:
                f.write(page_source)
            
            # 视频提取模式
            video_patterns = [
                r'src="(https://[^"]+\.mp4[^"]*)"',
                r'"playAddr":"(https://[^"]+)"',
                r'"url":"(https://[^"]+\.mp4[^"]*)"',
                r'"url_list":\["([^"]+)"\]',
                r'"play_addr":\{"uri":"[^"]+","url_list":\["([^"]+)"\]',
                r'"video":\{[^}]*"play_addr":\{[^}]*"url_list":\["([^"]+)"',
                r'"download_addr":\{[^}]*"url_list":\["([^"]+)"'
            ]
            
            # 查找视频URL
            for pattern in video_patterns:
                matches = re.findall(pattern, page_source)
                if matches:
                    for match in matches:
                        candidate = match.replace('\\u002F', '/').replace('\\/', '/')
                        if "http" in candidate and (".mp4" in candidate or "douyin" in candidate):
                            logger.info("成功从页面提取到视频链接")
                            return candidate
            
            # 尝试从视频元素中获取
            selectors = ["video", "video source", "[data-e2e='video-player'] video"]
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        src = elem.get_attribute("src")
                        if src and ("http" in src):
                            logger.info("成功从视频元素中提取到链接")
                            return src
                except:
                    continue
                    
            logger.warning("未能从页面中提取到视频链接")
            return None
        except Exception as e:
            logger.error(f"浏览器访问页面失败: {e}")
            return None
    
    def download_video(self, url, save_path=None):
        """下载抖音视频"""
        if save_path is None:
            save_path = os.path.join(self.save_path, f"douyin_{int(time.time())}.mp4")
            
        # 获取视频URL
        video_url = None
        
        # 使用Selenium方法获取视频
        if self.use_selenium:
            video_url = self._get_video_info_via_selenium(url)
            
        # 如果Selenium方法失败，尝试其他方法
        if not video_url:
            logger.info("尝试使用备用方法提取视频链接")
            try:
                # 配置代理
                proxies = None
                if self.proxy:
                    proxies = {
                        'http': self.proxy,
                        'https': self.proxy
                    }
                
                # 重定向处理
                response = requests.get(url, headers=self.headers, allow_redirects=True, proxies=proxies)
                html_content = response.text
                
                # 尝试从HTML内容中提取视频URL
                video_patterns = [
                    r'src="(https://[^"]+\.mp4[^"]*)"',
                    r'"playAddr":"(https://[^"]+)"',
                    r'"url":"(https://[^"]+\.mp4[^"]*)"',
                ]
                
                for pattern in video_patterns:
                    matches = re.findall(pattern, html_content)
                    if matches:
                        for match in matches:
                            candidate = match.replace('\\u002F', '/').replace('\\/', '/')
                            if "http" in candidate and (".mp4" in candidate or "douyin" in candidate):
                                video_url = candidate
                                logger.info("成功从网页内容中提取到视频链接")
                                break
                    if video_url:
                        break
            except Exception as e:
                logger.error(f"备用方法提取失败: {e}")
                
        # 如果无法获取视频URL，返回None
        if not video_url:
            logger.error("无法获取视频URL，下载失败")
            return None
            
        # 下载视频
        try:
            logger.info(f"开始下载视频到 {save_path}")
            
            # 配置代理
            proxies = None
            if self.proxy:
                proxies = {
                    'http': self.proxy,
                    'https': self.proxy
                }
                
            response = requests.get(video_url, headers=self.headers, stream=True, proxies=proxies)
            total_size = int(response.headers.get('content-length', 0))
            
            with open(save_path, 'wb') as f:
                if total_size > 0:
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=1024*1024):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            progress = (downloaded / total_size) * 100
                            if downloaded % (5*1024*1024) == 0:  # 每5MB报告一次
                                logger.info(f"下载进度: {progress:.1f}%")
                else:
                    # 如果无法获取内容长度，直接下载
                    for chunk in response.iter_content(chunk_size=1024*1024):
                        if chunk:
                            f.write(chunk)
            
            logger.info(f"视频下载完成: {save_path}")
            return save_path
        except Exception as e:
            logger.error(f"下载视频失败: {e}")
            if os.path.exists(save_path):
                os.remove(save_path)
            return None
    
    def process_url(self, url, save_path=None):
        """处理URL并下载视频"""
        if not url:
            return None
            
        # 直接下载
        return self.download_video(url, save_path)
        
    def process_urls(self, urls, max_workers=4):
        """批量处理URL"""
        if not urls:
            return []
            
        successful_downloads = []
        failed_urls = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {executor.submit(self.process_url, url): url for url in urls}
            for future in future_to_url:
                url = future_to_url[future]
                try:
                    result = future.result()
                    if result:
                        successful_downloads.append(result)
                    else:
                        failed_urls.append(url)
                except Exception:
                    failed_urls.append(url)
        
        logger.info(f"下载完成: 成功 {len(successful_downloads)} 个, 失败 {len(failed_urls)} 个")
        
        return successful_downloads

# 使用示例
def download_video_method(url, save_path, browser_type="edge", proxy=None, use_local_driver=False):
    """下载抖音视频
    
    参数:
        url: 抖音视频链接
        save_path: 保存路径
        browser_type: 浏览器类型，可选值为"edge", "firefox", "chrome" 
        proxy: HTTP代理地址，格式为"http://ip:port"或"socks5://ip:port"
        use_local_driver: 是否使用本地驱动而不是自动下载
    """
    if not SELENIUM_AVAILABLE:
        print("请先安装Selenium: pip install selenium webdriver-manager")
        return None
        
    try:
        downloader = DouyinDownloader(
            save_path="./download_videos", 
            browser_type=browser_type, 
            proxy=proxy,
            use_local_driver=use_local_driver
        )
        video_path = downloader.process_url(url, save_path)
        
        print(f"成功下载: {downloader.success_count} 个视频")
        print(f"失败: {downloader.fail_count} 个视频")
        
        return video_path
    except Exception as e:
        print(f"下载视频时出错: {str(e)}")
        traceback.print_exc()
        return None

# 示例用法
if __name__ == "__main__":
    url = "https://v.douyin.com/ABC123/"  # 替换为实际的抖音视频链接
    save_path = "video.mp4"
    video_path = download_video_method(url, save_path, browser_type="edge")
    if video_path:
        print(f"视频已下载到: {video_path}")
    else:
        print("视频下载失败") 