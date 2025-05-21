from MYTTS import *
import re
import subprocess
from mutagen.mp3 import MP3
import uuid
import os
import logging
from make_image import *

# 配置基本的日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 配置subprocess启动信息以隐藏窗口
startupinfo = subprocess.STARTUPINFO()
startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

# 获取mp3音频文件的时间长度
def get_mp3_length(file_path):
    if os.path.exists(file_path):
        try:
            audio = MP3(file_path)
            return audio.info.length
        except Exception as e:
            logger.error(f"获取MP3长度失败: {e}")
            return 0
    else:
        logger.warning(f"文件不存在: {file_path}")
        return 0

def split_audio(input_file, output_file, ffmpeg_path):
    """去除音频前后的静音"""
    cmd = [
        ffmpeg_path,
        '-hide_banner',
        '-loglevel', 'warning',
        '-i', input_file,
        '-filter_complex',
        'silenceremove=start_periods=1:start_duration=0:start_threshold=-50dB:detection=peak,areverse,silenceremove=start_periods=1:start_duration=0:start_threshold=-50dB:detection=peak,areverse',
        '-ar', '44100',
        '-ac', '2',
        output_file,
        '-y'
    ]
    try:
        subprocess.run(cmd, check=True, startupinfo=startupinfo, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        logger.error(f"音频分割失败: {e}")
        # 如果分割失败，复制原文件作为输出
        if os.path.exists(input_file):
            import shutil
            shutil.copy(input_file, output_file)

def process_audio_file(input_file, output_file, ffmpeg_path, task_id, cleanup=True):
    """处理音频文件的通用方法"""
    idx = str(uuid.uuid4())
    temp_file = f"./cache/{task_id}/gga{idx}.mp3"
    
    try:
        # 分割音频
        split_audio(input_file, temp_file, ffmpeg_path)
        
        # 添加静音尾部
        cmd = [
            ffmpeg_path, "-y", "-i", os.path.abspath(temp_file), "-f", "lavfi", "-t", '0.3',
            "-i", "anullsrc=r=44100:cl=stereo", 
            "-filter_complex", "[0][1]concat=n=2:v=0:a=1[out]", 
            "-map", "[out]", output_file
        ]
        subprocess.run(cmd, check=True, startupinfo=startupinfo, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if cleanup and os.path.exists(temp_file):
            os.remove(temp_file)
            
        return get_mp3_length(output_file)
    except Exception as e:
        logger.error(f"处理音频失败: {e}")
        if os.path.exists(input_file) and not os.path.exists(output_file):
            import shutil
            shutil.copy(input_file, output_file)
        return get_mp3_length(output_file)
    finally:
        # 清理临时文件
        if cleanup:
            if os.path.exists(input_file):
                os.remove(input_file)
            if os.path.exists(temp_file):
                os.remove(temp_file)

async def generate_audio_useEdgeTTS(text, output_path, ffmpeg_path, task_id):
    """使用EdgeTTS生成音频"""
    idx = str(uuid.uuid4())
    temp_wav = f"./cache/{task_id}/{idx}.wav"
    temp_mp3 = f"./cache/{task_id}/ggb{idx}.mp3"
    
    try:
        # 生成WAV文件
        await edgeTTS(text, 'zh-CN-XiaoxiaoNeural', temp_wav)
        
        # 转换为MP3
        cmd = [ffmpeg_path, "-y", "-i", temp_wav, temp_mp3]
        subprocess.run(cmd, check=True, startupinfo=startupinfo, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # 处理音频
        return process_audio_file(temp_mp3, output_path, ffmpeg_path, task_id)
    except Exception as e:
        logger.error(f"EdgeTTS音频生成失败: {e}")
        return 0

def generate_audio_useZureAPI(task_id, text, reg, apikey, ffmpeg_path, output_path, voice):
    """使用Azure API生成音频"""
    idx = str(uuid.uuid4())
    temp_mp3 = f"./cache/{task_id}/ggb{idx}.mp3"
    
    try:
        azureTTS(apikey=apikey, text=text, voice=voice, reg=reg, output_path=temp_mp3)
        return process_audio_file(temp_mp3, output_path, ffmpeg_path, task_id)
    except Exception as e:
        logger.error(f"Azure API调用失败: {e}")
        return 0

def generate_audio_useAliAPI(task_id, text, ffmpeg_path, output_path):
    """使用阿里云API生成音频"""
    idx = str(uuid.uuid4())
    temp_wav = f"./cache/{task_id}/{idx}.wav"
    temp_mp3 = f"./cache/{task_id}/ggb{idx}.mp3"
    
    try:
        aliTTS(text=text, output_path=temp_wav)
        
        # 转换为MP3
        cmd = [ffmpeg_path, "-y", "-i", temp_wav, temp_mp3]
        subprocess.run(cmd, check=True, startupinfo=startupinfo, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # 处理音频
        return process_audio_file(temp_mp3, output_path, ffmpeg_path, task_id)
    except Exception as e:
        logger.error(f"阿里云API调用失败: {e}")
        return 0

def generate_audio_useXtts(text, output_path, ffmpeg_path, task_id):
    """使用XTTS生成音频"""
    idx = str(uuid.uuid4())
    temp_wav = f"./cache/{task_id}/{idx}.wav"
    temp_mp3 = f"./cache/{task_id}/ggb{idx}.mp3"
    
    try:
        # 这里XTTS实现被注释了，保持原样
        #tts_xtts(text, output_path=temp_wav)
        logger.info('XTTS API调用未实现')
        
        # 如果XTTS实现，则处理以下代码
        if os.path.exists(temp_wav):
            # 转换为MP3
            cmd = [ffmpeg_path, "-y", "-i", temp_wav, temp_mp3]
            subprocess.run(cmd, check=True, startupinfo=startupinfo, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # 处理音频
            return process_audio_file(temp_mp3, output_path, ffmpeg_path, task_id)
        return 0
    except Exception as e:
        logger.error(f"XTTS调用失败: {e}")
        return 0

def generate_audio_useTencentAPI(text, output_path, ffmpeg_path, task_id):
    """使用腾讯云API生成音频"""
    idx = str(uuid.uuid4())
    temp_mp3 = f"./cache/{task_id}/{idx}.mp3"
    temp_mp3_2 = f"./cache/{task_id}/ggb{idx}.mp3"
    
    try:
        tencentTTS(text=text, output_path=temp_mp3)
        
        # 转换为标准格式
        cmd = [ffmpeg_path, "-y", "-i", temp_mp3, temp_mp3_2]
        subprocess.run(cmd, check=True, startupinfo=startupinfo, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # 处理音频，这里使用0.1秒而不是0.3秒的静音
        process_result = process_audio_file(temp_mp3_2, output_path, ffmpeg_path, task_id, cleanup=False)
        
        # 清理临时文件
        for file in [temp_mp3, temp_mp3_2]:
            if os.path.exists(file):
                os.remove(file)
                
        return process_result
    except Exception as e:
        logger.error(f"腾讯云API调用失败: {e}")
        return 0

def create_video(
    input_video_path,
    output_video_path,
    chinese_text,
    font_path_chinese,
    start_time,
    end_time,
    chinese_text_size=10,
    chinese_text_color=(0,0,0),
    chinese_text_posotion=1.75,
    line_spacing=1.5
    ):
    """处理视频的每一帧，添加文字和模糊背景"""
    logger.info(f"处理文字：{chinese_text[:20]}... 时间：{start_time}-{end_time}")
    
    # 打开输入视频
    cap = cv2.VideoCapture(input_video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"无法打开视频文件 {input_video_path}")
    
    # 获取视频属性
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_duration = total_frames / fps  # 视频总时长（秒）
    
    # 处理开始时间（如果大于视频长度则取模）
    if start_time > video_duration:
        start_time = start_time % video_duration
        logger.warning(f"开始时间超过视频长度，使用取模后的时间 {start_time} 秒")
    
    # 计算开始和结束帧
    start_frame = int(start_time * fps)
    if end_time is not None:
        if end_time > video_duration:
            end_time = end_time % video_duration
            logger.warning(f"结束时间超过视频长度，使用取模后的时间 {end_time} 秒")
        end_frame = int(end_time * fps)
    else:
        end_frame = total_frames
        
    # 计算需要处理的总帧数
    if start_frame > end_frame:
        target_frames = total_frames - start_frame + end_frame
    else:
        target_frames = end_frame - start_frame
    
    # 设置开始帧
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    
    # 创建视频写入器
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_video_path, fourcc, fps, (width, height))
    
    try:
        total_processed_frames = 0
        # 每100帧显示一次进度
        log_interval = max(1, target_frames // 10)
        
        while total_processed_frames < target_frames:
            ret, frame = cap.read()
            if not ret:
                # 如果到达视频末尾，重新开始
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = cap.read()
                if not ret:
                    break
                    
            # 处理当前帧
            processed_frame = create_static_text_image(
                frame,
                chinese_text,
                font_path_chinese,
                chinese_text_size,
                chinese_text_color,
                chinese_text_posotion,
                line_spacing
            )
            
            # 写入处理后的帧
            out.write(processed_frame)
            total_processed_frames += 1
            
            # 定期显示进度
            if total_processed_frames % log_interval == 0 or total_processed_frames == target_frames:
                progress = (total_processed_frames / target_frames) * 100
                logger.info(f"视频处理进度: {progress:.1f}% ({total_processed_frames}/{target_frames})")
            
    finally:
        # 释放资源
        cap.release()
        out.release()
            
    logger.info(f"视频处理完成: {output_video_path}")

def replace_prohibited_words(text, file_path):
    """替换禁用词"""
    prohibited_words_dict = {}
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            prohibited_words_dict = json.load(file)
    except FileNotFoundError:
        logger.warning(f"禁用词文件未找到: {file_path}")
        return text
    except json.JSONDecodeError:
        logger.warning(f"禁用词文件格式有误: {file_path}")
        return text
        
    for word, replacement in prohibited_words_dict.items():
        text = text.replace(word, replacement)
    return text

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
        '"': '"',  # 中文双引号
        "'": "'",  # 英文单引号
        "'":"'",
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
        if all_sentences[i] and all_sentences[i][-1] in sentence_enders:
            all_sentences[i] = all_sentences[i][0:-1]
            
    return all_sentences

def merge_VA(input_files, output_file, ffmpeg_path, filelist_path):
    """合并音频或视频文件"""
    if not input_files:
        logger.error("没有文件可以合并")
        return False
        
    # 过滤掉不存在的文件
    valid_files = [file for file in input_files if os.path.exists(file)]
    if not valid_files:
        logger.error("没有有效的文件可以合并")
        return False
    
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # 创建文件列表
            with open(filelist_path, 'w', encoding='utf-8') as f:
                for file in valid_files:
                    f.write(f"file '{file}'\n")
            
            # 执行合并命令
            command = [
                ffmpeg_path,
                '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', filelist_path,
                '-c', 'copy',
                output_file
            ]
            
            subprocess.run(
                command,
                check=True,
                startupinfo=startupinfo,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            logger.info(f"成功合并 {len(valid_files)} 个文件到 {output_file}")
            return True
            
        except subprocess.CalledProcessError as e:
            retry_count += 1
            logger.warning(f"合并文件失败 (尝试 {retry_count}/{max_retries}): {e}")
            if retry_count == max_retries:
                logger.error(f"无法合并文件到: {output_file}")
                return False
            time.sleep(1)  # 等待1秒后重试
        except Exception as e:
            logger.error(f"合并文件时发生未知错误: {e}")
            return False

