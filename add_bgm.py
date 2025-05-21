import subprocess
import os
import tempfile
startupinfo = subprocess.STARTUPINFO()
startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
def add_bgm_ffmpeg(
    video_path: str,
    music_path: str,
    output_path: str,
    music_volume: float = 0.5,
    keep_original_audio: bool = True
):
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"未找到视频文件：{video_path}")
    if not os.path.exists(music_path):
        raise FileNotFoundError(f"未找到音乐文件：{music_path}")

    # 创建一个临时文件名用于重复音乐处理（因为 -stream_loop 只能用于输入文件）
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio:
        temp_music_path = temp_audio.name

    # 先获取视频时长
    def get_duration(path):
        result = subprocess.run(
            ["./ffmpeg/bin/ffprobe.exe", "-v", "error", "-show_entries",
             "format=duration", "-of",
             "default=noprint_wrappers=1:nokey=1", path],
            startupinfo=startupinfo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return float(result.stdout.strip())

    video_duration = get_duration(video_path)
    music_duration = get_duration(music_path)

    if music_duration < video_duration:
        # 重复音乐音频以满足视频长度
        loop_count = int(video_duration // music_duration) + 1
        # 使用concat协议拼接音频
        with open("concat_list.txt", "w", encoding="utf-8") as f:
            for _ in range(loop_count):
                f.write(f"file '{os.path.abspath(music_path)}'\n")
        subprocess.run([
            "./ffmpeg/bin/ffmpeg.exe", "-y", "-f", "concat", "-safe", "0", "-i", "concat_list.txt",
            "-t", str(video_duration), "-c", "copy", temp_music_path
        ], startupinfo=startupinfo, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        os.remove("concat_list.txt")
    else:
        # 音乐比视频长，直接截断
        subprocess.run([
            "./ffmpeg/bin/ffmpeg.exe", "-y", "-i", music_path, "-t", str(video_duration),
            "-c", "copy", temp_music_path
        ], startupinfo=startupinfo, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # 开始合成视频和背景音乐
    cmd = [
        "./ffmpeg/bin/ffmpeg.exe", "-y",
        "-i", video_path,
        "-i", temp_music_path,
        "-filter_complex",
        f"[1:a]volume={music_volume}[bgm];" +
        (f"[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]" if keep_original_audio
         else f"[bgm]anull[aout]"),
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-shortest",
        output_path
    ]
    subprocess.run(cmd, check=True, startupinfo=startupinfo, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    os.remove(temp_music_path)
