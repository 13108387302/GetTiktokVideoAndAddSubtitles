from get_video import *
from flask import Flask, request, jsonify
import threading
from threading import Lock
import uuid
import shutil
import logging
import traceback
from add_bgm import add_bgm_ffmpeg
from douyin_downloader import download_video_method

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='app.log',
    filemode='a'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# 进度变量
progress_dict = {}
error_dict = {}  # 用于存储任务错误信息
progress_lock = Lock()  # 进度锁
startupinfo = subprocess.STARTUPINFO()
startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

# 生成视频的函数
def generate_video_method(
    s,
    tmls,
    t,
    stage_weights,
    task_id,
    sentences,
    backGround_image_path="./background.jpg",
    ffmpeg_path="./ffmpeg/bin/ffmpeg.exe",
    font_path_chinese=r"C:\\Windows\\Fonts\\simsun.ttc",
    chinese_text_size=10,
    chinese_text_color=(0,0,0),
    chinese_text_posotion=1.75,
    line_spacing=1.5
    ):
    try:
        with progress_lock:
            progress_dict[task_id] += stage_weights[0]
        
        output_paths = []
        lens = len(sentences)
        for idx, sentence in enumerate(sentences):
            output_path = os.path.abspath(f'./cache/{task_id}/output_{t}_{idx}.mp4')
            output_paths.append(output_path)
            conf = {
                "chinese_text_size": chinese_text_size,
                "chinese_text_color": chinese_text_color,
                "chinese_text_posotion": chinese_text_posotion,
                "line_spacing": line_spacing,
                "input_video_path": backGround_image_path,
                "chinese_text": sentence,
                "output_video_path": output_path,
                "font_path_chinese": font_path_chinese,
                "start_time": tmls[idx+s][0],
                "end_time": tmls[idx+s][1]
            }
            create_video(**conf)
            with progress_lock:
                progress_dict[task_id] += (1/lens)*stage_weights[1]
        
        # 合并视频片段
        merge_VA(output_paths, f'./cache/{task_id}/finalPicture_{t}.mp4', ffmpeg_path, f'./cache/{task_id}/file_{t}.txt')
        with progress_lock:
            progress_dict[task_id] += stage_weights[2]
    except Exception as e:
        error_msg = f"视频生成阶段出错 (线程 {t}): {str(e)}"
        logger.error(error_msg)
        with progress_lock:
            error_dict[task_id] = error_msg
        raise

def split_integer(num, n):
    """将整数num均匀分成n份"""
    base, remainder = divmod(num, n)
    x = [base + 1] * remainder + [base] * (n - remainder)
    y = [0]
    for i in range(n):
        y.append(y[i]+x[i])
    return y

# 抖音视频下载API端点
@app.route('/download_douyin', methods=['POST'])
def download_douyin():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '无效的请求数据'}), 400
            
        # 验证必要参数
        if not data.get('backGround_image_path2') or not data.get('backGround_image_path2').startswith('http'):
            return jsonify({'error': '抖音链接无效'}), 400
            
        # 确定使用的浏览器类型
        browser_type = data.get('browser_type', 'edge')  # 默认使用Edge浏览器
        # 获取代理设置（如果有）
        proxy = data.get('proxy')
        # 判断是否使用本地驱动
        use_local_driver = data.get('use_local_driver', False)
        
        logger.info(f"开始下载抖音视频: {data.get('backGround_image_path2')}，使用浏览器: {browser_type}, 代理: {proxy if proxy else '无'}, 使用本地驱动: {use_local_driver}")
        
        try:
            # 确保下载目录存在
            os.makedirs('./download_videos', exist_ok=True)
            
            # 生成唯一文件名
            save_path = f'./download_videos/douyin_{str(uuid.uuid4())[:8]}.mp4'
            
            # 使用下载器下载视频，传入浏览器类型、代理和本地驱动选项
            video_path = download_video_method(
                data.get('backGround_image_path2'), 
                save_path, 
                browser_type, 
                proxy,
                use_local_driver
            )
            
            if not video_path or not os.path.exists(video_path):
                return jsonify({'error': '视频下载失败，未能获取视频文件'}), 500
                
            logger.info(f"抖音视频下载成功: {video_path}")
            
            # 返回视频路径
            return jsonify({
                'message': f'视频下载成功，保存位置: {os.path.abspath(video_path)}',
                'video_path': video_path
            }), 200
            
        except Exception as e:
            error_msg = f"抖音视频下载失败: {str(e)}"
            logger.error(error_msg)
            return jsonify({'error': error_msg}), 500
            
    except Exception as e:
        return jsonify({'error': f"处理请求失败: {str(e)}"}), 500

# 后端接口：用于上传数据并开始生成视频
@app.route('/upload', methods=['POST'])
def upload_file():
    task_id = str(uuid.uuid4())
    with progress_lock:
        progress_dict[task_id] = 0
        error_dict[task_id] = None
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '无效的请求数据'}), 400
            
        # 参数验证
        required_fields = ['sentences', 'ffmpeg_path', 'save_path']
        for field in required_fields:
            if field not in data or not data.get(field):
                return jsonify({'error': f'缺少必要参数: {field}'}), 400
        
        logger.info(f"任务 {task_id} 开始处理")
        
        # 处理句子
        sentences = [i for i in data.get('sentences') if i]
        if not sentences:
            return jsonify({'error': '没有有效的句子内容'}), 400
            
        # 设置线程数
        lens = len(sentences)
        thnum = min(20, lens)  # 最多20个线程
        
        # 分配权重
        x = split_integer(lens, thnum)
        stage_weights = [5, 50, 10]
        stage_weights = [w/thnum for w in stage_weights]
        
        # 初始化路径列表
        audio_paths = []
        video_paths = []
        
        # 创建缓存目录
        cache_dir = f'./cache/{task_id}'
        try:
            os.makedirs(cache_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"创建缓存目录失败: {str(e)}")
            return jsonify({'error': f'创建缓存目录失败: {str(e)}'}), 500
        
        # 下载视频函数
        def download_video():
            try:
                if data.get('trans_method') == "抖音爬取":
                    if not data.get('backGround_image_path2'):
                        raise ValueError("抖音链接为空")
                    
                    # 设置进度状态
                    with progress_lock:
                        progress_dict[task_id] = 1  # 设置为1%表示任务已开始
                        error_dict[task_id] = "正在从抖音获取视频，请稍候..."
                    
                    # 添加一个线程使进度条来回滑动，显示下载正在进行
                    download_in_progress = [True]  # 用列表包装布尔值以便在内部函数中修改
                    def animate_progress():
                        animation_range = [1, 4]  # 在1%到4%之间波动
                        direction = 1  # 初始方向是向上
                        while download_in_progress[0]:
                            with progress_lock:
                                current = progress_dict[task_id]
                                # 仅在状态正常且未完成时动画
                                if current >= 0 and current < 5:
                                    if current >= animation_range[1]:
                                        direction = -1  # 达到上限，改变方向
                                    elif current <= animation_range[0]:
                                        direction = 1   # 达到下限，改变方向
                                    
                                    # 更新进度，小幅度波动
                                    progress_dict[task_id] = current + 0.2 * direction
                            
                            time.sleep(0.3)  # 控制动画速度
                    
                    # 启动动画线程
                    animation_thread = threading.Thread(target=animate_progress, daemon=True)
                    animation_thread.start()
                    
                    # 获取浏览器类型，默认为Edge
                    browser_type = data.get('browser_type', 'edge')
                    # 获取代理设置（如果有）
                    proxy = data.get('proxy')
                    # 判断是否使用本地驱动
                    use_local_driver = data.get('use_local_driver', False)
                    logger.info(f"开始从抖音下载视频: {data.get('backGround_image_path2')}，使用浏览器: {browser_type}，代理: {proxy if proxy else '无'}，使用本地驱动: {use_local_driver}")
                    
                    try:
                        video_path = download_video_method(
                            data.get('backGround_image_path2'), 
                            f'./download_videos/{task_id}.mp4', 
                            browser_type, 
                            proxy,
                            use_local_driver
                        )
                        
                        # 停止动画线程
                        download_in_progress[0] = False
                        
                        if not video_path or not os.path.exists(video_path):
                            raise ValueError(f"视频下载失败，未获取到视频文件")
                        
                        # 下载完成，更新状态
                        with progress_lock:
                            progress_dict[task_id] = 5  # 设置为5%表示下载完成，开始后续处理
                            # 在状态消息中显示视频保存位置
                            error_dict[task_id] = f"视频下载完成，保存位置: {os.path.abspath(video_path)}"
                        
                        logger.info(f"抖音视频下载完成: {video_path}")
                        return video_path
                    except Exception as e:
                        # 停止动画线程
                        download_in_progress[0] = False
                        
                        error_msg = f"抖音视频下载失败: {str(e)}"
                        logger.error(error_msg)
                        with progress_lock:
                            error_dict[task_id] = error_msg
                            progress_dict[task_id] = -1  # 表示任务出错
                        raise ValueError(error_msg)
                else:
                    video_path = data.get('backGround_image_path')
                    if not os.path.exists(video_path):
                        raise ValueError(f"指定的视频文件不存在: {video_path}")
                    return video_path
            except Exception as e:
                error_msg = f"视频获取失败: {str(e)}"
                logger.error(error_msg)
                with progress_lock:
                    error_dict[task_id] = error_msg
                    progress_dict[task_id] = -1  # 表示任务出错
                raise
        
        # 生成语音并获取时长
        def generate_audio():
            currentTime = 0
            tmls = []
            try:
                for idx, sentence in enumerate(sentences):
                    # 确定该句子对应的线程索引
                    t = next(j-1 for j in range(len(x)) if idx < x[j])
                    
                    audio_path = os.path.abspath(f'{cache_dir}/audio_{t}_{idx}.mp3')
                    audio_paths.append(audio_path)
                    
                    try:
                        logger.info(f"开始生成语音: {sentence[:20]}...")
                        # 生成语音
                        duration = generate_audio_useTencentAPI(sentence, audio_path, data.get('ffmpeg_path'), task_id)
                        
                        if not os.path.exists(audio_path):
                            raise ValueError(f"生成的语音文件不存在: {audio_path}")
                        
                        # 记录时间戳
                        tmls.append([currentTime, currentTime+duration])
                        currentTime += duration
                        
                        # 更新进度
                        with progress_lock:
                            progress_dict[task_id] += 25/len(sentences)
                    except Exception as e:
                        error_msg = f"语音生成失败 ({idx+1}/{len(sentences)}): {str(e)}"
                        logger.error(error_msg)
                        with progress_lock:
                            error_dict[task_id] = error_msg
                        raise
                return tmls
            except Exception as e:
                with progress_lock:
                    if not error_dict[task_id]:
                        error_dict[task_id] = f"语音处理过程出错: {str(e)}"
                raise
        
        # 主处理函数
        def process_task():
            try:
                start_time = time.time()
                
                # 下载或获取视频
                movie_path = download_video()
                
                # 生成语音
                tmls = generate_audio()
                
                # 检查是否有错误
                with progress_lock:
                    if error_dict[task_id]:
                        raise Exception(error_dict[task_id])
                
                # 生成视频片段
                threads = []
                for i in range(thnum):
                    video_paths.append(os.path.abspath(f'{cache_dir}/finalPicture_{i}.mp4'))
                    thread = threading.Thread(
                        target=generate_video_method,
                        args=(
                            x[i],
                            tmls,
                            i,
                            stage_weights,
                            task_id,
                            sentences[x[i]:x[i+1]],
                            movie_path,
                            data.get('ffmpeg_path'),
                            data.get('font_path_chinese'),
                            int(data.get('chinese_text_size')),
                            tuple(data.get('chinese_text_color')),
                            float(data.get('chinese_text_position')),
                            float(data.get('line_spacing')),
                        )
                    )
                    threads.append(thread)
                    thread.start()
                
                # 等待所有线程完成
                for thread in threads:
                    thread.join()
                
                # 检查是否有错误
                with progress_lock:
                    if error_dict[task_id]:
                        raise Exception(error_dict[task_id])
                
                # 合并音频
                logger.info("开始合并音频文件")
                merge_VA(audio_paths, f'{cache_dir}/finalAudio.mp3', data.get('ffmpeg_path'), f'{cache_dir}/filelist.txt')
                
                # 合并视频
                logger.info("开始合并视频文件")
                with progress_lock:
                    progress_dict[task_id] = 80
                
                merge_VA(video_paths, f'{cache_dir}/finalPicture.mp4', data.get('ffmpeg_path'), f'{cache_dir}/filelist_v.txt')
                
                with progress_lock:
                    progress_dict[task_id] = 90
                
                # 合并视频和音频
                logger.info("开始合并视频和音频")
                final_video_no_bgm = f"{cache_dir}/final_video_nobgm.mp4"
                command = [
                    data.get('ffmpeg_path'),
                    '-y', 
                    '-i', os.path.abspath(f'{cache_dir}/finalPicture.mp4'),
                    '-i', os.path.abspath(f'{cache_dir}/finalAudio.mp3'),
                    '-c:v', 'copy',
                    '-c:a', 'aac',
                    '-strict', 'experimental',
                    final_video_no_bgm
                ]
                
                process = subprocess.run(command, startupinfo=startupinfo, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if process.returncode != 0:
                    error_msg = f"视频和音频合并失败"
                    logger.error(error_msg)
                    with progress_lock:
                        error_dict[task_id] = error_msg
                    raise Exception(error_msg)
                
                # 添加背景音乐
                logger.info("开始添加背景音乐")
                final_path = f"{data.get('save_path')}/final_video_{task_id}.mp4"
                
                if not os.path.exists(final_video_no_bgm):
                    raise Exception("合成的无背景音乐视频文件不存在")
                
                # 确保保存目录存在
                os.makedirs(os.path.dirname(final_path), exist_ok=True)
                
                # 添加背景音乐
                add_bgm_ffmpeg(final_video_no_bgm, data.get('bgm'), final_path, music_volume=data.get("bgm_volumn"))
                
                # 检查最终输出文件是否存在
                if not os.path.exists(final_path):
                    raise Exception(f"添加背景音乐后的最终视频文件未生成")
                
                with progress_lock:
                    progress_dict[task_id] = 100
                
                # 清理缓存
                logger.info(f"任务 {task_id} 完成，清理临时文件")
                try:
                    if os.path.exists(cache_dir):
                        shutil.rmtree(cache_dir)
                    
                    # 如果是抖音爬取的视频，同时删除下载的视频文件
                    if data.get('trans_method') == "抖音爬取" and movie_path and os.path.exists(movie_path):
                        os.remove(movie_path)
                except Exception as e:
                    logger.error(f"清理资源失败: {str(e)}")
                
                logger.info(f"任务 {task_id} 成功完成，耗时: {time.time() - start_time:.2f}秒")
                
            except Exception as e:
                error_msg = f"视频处理过程出错: {str(e)}"
                logger.error(error_msg)
                with progress_lock:
                    error_dict[task_id] = error_msg
                    progress_dict[task_id] = -1
                
                # 清理资源
                try:
                    if os.path.exists(cache_dir):
                        shutil.rmtree(cache_dir)
                    
                    # 如果是抖音爬取的视频，同时删除下载的视频文件
                    if data.get('trans_method') == "抖音爬取" and 'movie_path' in locals() and movie_path and os.path.exists(movie_path):
                        os.remove(movie_path)
                except Exception as cleanup_err:
                    logger.error(f"清理资源失败: {str(cleanup_err)}")
        
        # 启动处理线程
        threading.Thread(target=process_task, daemon=True).start()
        return jsonify({'message': '视频生成已开始！', 'task_id': task_id}), 200
    
    except Exception as e:
        error_msg = f"初始化处理失败: {str(e)}"
        logger.error(error_msg)
        with progress_lock:
            error_dict[task_id] = error_msg
            progress_dict[task_id] = -1
        return jsonify({'error': error_msg, 'task_id': task_id}), 500

@app.route('/progress/<task_id>', methods=['GET'])
def get_progress(task_id):
    with progress_lock:
        progress = progress_dict.get(task_id, 0)
        error = error_dict.get(task_id)
    
    # 如果有错误，返回错误信息
    if error:
        return jsonify({
            'progress': -1,
            'error': error
        })
    
    return jsonify({
        'progress': min(int(progress), 100),
        'error': None
    })

def start():
    app.run(debug=False)
