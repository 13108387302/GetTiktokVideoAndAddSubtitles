import time
import threading
import sys
import nls
import json
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
import asyncio
import edge_tts
import azure.cognitiveservices.speech as speechsdk
import base64
import requests
import hmac
import hashlib
import random
import string
class TencentTTS:
    def __init__(self, secret_id, secret_key, region="ap-guangzhou", voice_type=1001):
        """
        初始化腾讯云TTS服务
        :param secret_id: 腾讯云API密钥ID
        :param secret_key: 腾讯云API密钥Key
        :param region: 服务区域，默认为广州
        :param voice_type: 音色ID，默认1001（智瑜）
        """
        self.secret_id = secret_id
        self.secret_key = secret_key
        self.region = region
        self.voice_type = voice_type
        self.endpoint = "tts.tencentcloudapi.com"
        self.version = "2019-08-23"
        self.service = "tts"

    def _get_signature(self, params):
        """
        生成签名
        """
        # 1. 对参数排序
        sorted_params = sorted(params.items(), key=lambda x: x[0])
        
        # 2. 拼接参数字符串
        param_str = '&'.join([f"{k}={v}" for k, v in sorted_params])
        
        # 3. 拼接签名串
        string_to_sign = f"POST{self.endpoint}/?{param_str}"
        
        # 4. 计算签名
        hmac_obj = hmac.new(
            self.secret_key.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha1
        )
        signature = base64.b64encode(hmac_obj.digest()).decode('utf-8')
        
        return signature
    
    def text_to_speech(self, text, output_path, speed=0, volume=0, project_id=0):
        """
        将文本转换为语音
        :param text: 要转换的文本
        :param output_path: 输出文件路径
        :param speed: 语速，范围[-2,2]，默认0
        :param volume: 音量，范围[-10,10]，默认0
        :param project_id: 项目ID，默认0
        :return: 是否成功
        """
        # 构建请求参数
        params = {
            "Action": "TextToVoice",
            "Version": self.version,
            "Region": self.region,
            "Text": text,
            "SessionId": ''.join(random.choices(string.ascii_letters + string.digits, k=16)),
            "ModelType": 1,
            "VoiceType": self.voice_type,
            "Speed": speed,
            "Volume": volume,
            "ProjectId": project_id,
            "Timestamp": int(time.time()),
            "Nonce": random.randint(1, 1000000),
            "SecretId": self.secret_id
        }

        # 生成签名
        signature = self._get_signature(params)
        params["Signature"] = signature

        # 发送请求
        try:
            response = requests.post(
                f"https://{self.endpoint}",
                data=params,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code == 200:
                result = response.json()
                if "Response" in result and "Audio" in result["Response"]:
                    # 解码音频数据并保存
                    audio_data = base64.b64decode(result["Response"]["Audio"])
                    with open(output_path, "wb") as f:
                        f.write(audio_data)
                    return True
                else:
                    print(f"转换失败: {result}")
                    return False
            else:
                print(f"请求失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"发生错误: {str(e)}")
            return False 

def tencentTTS(text,output_path):
    # 初始化TTS服务，设置音色
    tts = TencentTTS(
        secret_id="",
        secret_key="",
        voice_type=501006 # 设置音色，1001是智瑜
    )

    # 转换文本为语音
    success = tts.text_to_speech(
        text=text,
        output_path=output_path,
        volume=10
    )
    return success

def getAlitoken():
    # 创建AcsClient实例
    client = AcsClient(
       '',
       '',
       "cn-shanghai"
    );
    # 创建request，并设置参数。
    request = CommonRequest()
    request.set_method('POST')
    request.set_domain('nls-meta.cn-shanghai.aliyuncs.com')
    request.set_version('2019-02-28')
    request.set_action_name('CreateToken')
    try : 
       response = client.do_action_with_exception(request)
       jss = json.loads(response)
       if 'Token' in jss and 'Id' in jss['Token']:
          token = jss['Token']['Id']
          expireTime = jss['Token']['ExpireTime']
          return token
    except Exception as e:
       print(e)

       
class TestTts:
    def __init__(self,test_file, token,appkey,voice='zhiyuan',url="wss://nls-gateway-cn-shanghai.aliyuncs.com/ws/v1"):
        self.__test_file = test_file
        self.__test_voice=voice
        self.__test_url=url
        self.__test_token=token
        self.__test_appkey=appkey
    def start(self, text):
        self.__text = text
        self.__f = open(self.__test_file, "wb")
        self.__test_run().shutdown()
        self.__f.close()

    def test_on_data(self, data, *args):
        try:
            self.__f.write(data)
        except Exception as e:
            print("write data failed:", e)

    def __test_run(self):
        tts = nls.NlsSpeechSynthesizer(
            url=self.__test_url,
            token=self.__test_token,
            appkey=self.__test_appkey,
            on_data=self.test_on_data
        )
        tts.start(self.__text, aformat='wav', voice=self.__test_voice,pitch_rate=-75)
        return tts


def aliTTS(text,voice='Kenny',output_path='./out.wav',url="wss://nls-gateway-cn-shanghai.aliyuncs.com/ws/v1"):
    nls.enableTrace(True)
    t = TestTts(output_path,getAlitoken(),'XF4owsb11DeS6VNf',voice,url)
    t.start(text)

def azureTTS(
        apikey,
        reg,
        output_path,
        voice,
        text
    ):
    speech_config = speechsdk.SpeechConfig(subscription=apikey, region=reg)
    audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True,filename=output_path)
    speech_config.speech_synthesis_voice_name=voice
    speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3)  # 设置输出为 MP3 格式
    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
    speech_synthesis_result = speech_synthesizer.speak_text_async(text).get()
  
async def edgeTTS(text,voice,output_path):
    communicate = edge_tts.Communicate(text, voice=voice)
    await communicate.save(output_path)

