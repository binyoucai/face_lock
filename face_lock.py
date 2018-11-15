# -*- coding: utf-8 -*-
import os
import json
import base64
import cv2
import time
import datetime
import logging
import configparser
import shutil
import requests
import ctypes
import platform
import pyautogui as pag
from PIL import Image


class FaceLock(object):
    """ 人脸识别锁屏类 """
    LOCK_SCREEN = False
    POINT_X = POINT_Y = GET_AT_TIME = GET_FACE_TIME = FACE_MATCH_TIME = 0
    ALERT_TIMEOUT = 1000 * 4
    ALERT_TITLE = '人脸识别锁屏'

    def __init__(self):
        # 读取配置文件
        conf = configparser.ConfigParser()
        conf.read('./conf.ini', encoding='utf-8')
        self.AK = conf.get('setting', 'API_KEY')
        self.SK = conf.get('setting', 'SECRET_KEY')
        self.SCREEN_LOCK_LEVEL = float(conf.get('setting', 'SCREEN_LOCK_LEVEL'))
        self.LOCK_FACE_LIVENESS = float(conf.get('setting', 'LOCK_FACE_LIVENESS'))
        self.RETRY_TIME = int(conf.get('setting', 'RETRY_TIME'))
        if not os.path.exists('./log'):
            os.mkdir('./log')
        logName = './log/%s.log' % datetime.datetime.now().strftime('%Y_%m_%d')
        self.logger = logging.getLogger('face_lock_logger')
        fh = logging.FileHandler(logName, encoding='utf-8')
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('[%(asctime)s] - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        self.PLATFORM = platform.system()
        if self.PLATFORM not in ['Darwin', 'Windows']:
            self.logger.error('暂不支持您的系统：%s，程序退出' % self.PLATFORM)
            exit()
        # Access Token的有效期为30天（以秒为单位）
        self.ACCESS_TOKEN = self.__getAccessToken()

    # 获取接口access token
    def __getAccessToken(self):
        url = 'https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id=%s&client_secret=%s' % (
            self.AK, self.SK)
        try:
            request = requests.get(url)
            request.raise_for_status()
            res = json.loads(request.text)
            return res['access_token']
        except Exception as e:
            self.logger.error('获取access token失败:%s' % e)
            if self.GET_AT_TIME < self.RETRY_TIME:
                self.GET_AT_TIME += 1
                self.__getAccessToken()
            else:
                self.logger.error('获取access token失败，重试次数已用尽，程序退出')
                pag.alert(text='获取access token失败，重试次数已用尽，程序退出', title=self.ALERT_TITLE, timeout=self.ALERT_TIMEOUT)
                exit()

    # 开始检测
    def __checkIsMe(self):
        time.sleep(2)
        self.__getFace()
        res = self.__matchFace()
        self.logger.info('人脸识别结果：%s' % res)
        if res.get('error_msg', 0) == 'SUCCESS':
            score = res['result'].get('score')
            if float(score) < self.SCREEN_LOCK_LEVEL:
                self.logger.info('人脸识别相似度太小，或者不是真人，即将锁屏')
                self.__lockScreen()
            else:
                self.logger.info('人脸相似度：%s，不锁屏' % score)
        else:
            self.logger.error('人脸识别失败，可能没人在电脑面前，立即锁屏')
            self.__lockScreen(True)

    # 锁屏
    def __lockScreen(self, now=False):
        # 当前日期
        nowDate = datetime.datetime.now().strftime("%Y_%m_%d")
        # 当前时间
        nowTime = datetime.datetime.now().strftime("%H_%M_%S")
        # 保存导致锁屏的图片
        lock_picture_path = './picture/lock_pictures/%s' % nowDate
        if not os.path.exists(lock_picture_path):
            os.makedirs(lock_picture_path)
        new_path = '%s/%s.jpg' % (lock_picture_path, nowTime)
        shutil.move('./picture/face.jpg', new_path)
        res = 'NOW'
        if not now:
            res = pag.confirm('倒计时4秒，确定要锁屏吗?', title=self.ALERT_TITLE, timeout=self.ALERT_TIMEOUT)
            self.logger.info('confirm 弹框返回值: %s' % res)

        if res == 'OK' or res == 'Timeout' or res == 'NOW':
            self.LOCK_SCREEN = True
            if self.PLATFORM == 'Darwin':
                # macOS
                os.system('/System/Library/CoreServices/Menu\ Extras/User.menu/Contents/Resources/CGSession -suspend')
            elif self.PLATFORM == 'Windows':
                # windows
                dll = ctypes.WinDLL('user32.dll')
                dll.LockWorkStation()
            time.sleep(7)
            x, y = pag.position()
            self.logger.info('锁屏前鼠标坐标：x=%d，y=%d' % (x, y))
            self.POINT_X = x
            self.POINT_Y = y

    # 人脸识别匹配
    def __matchFace(self):
        url = 'https://aip.baidubce.com/rest/2.0/face/v3/match?access_token=%s' % self.ACCESS_TOKEN
        img1 = base64.b64encode(open('./picture/face.jpg', 'rb').read()).decode()
        img2 = base64.b64encode(open('./picture/myFace.jpg', 'rb').read()).decode()
        headers = {
            "Content-Type": "application/json"
        }
        data = [
            {
                'image': img1,
                'image_type': 'BASE64',

            },
            {
                'image': img2,
                'image_type': 'BASE64',

            }
        ]
        data = json.dumps(data)
        try:
            time.sleep(0.6)  # QPS限制
            request = requests.post(url, data=data, headers=headers)
            request.raise_for_status()
            res = request.text
            res = json.loads(res)
            err_code = res.get('error_code')
            print('成功', res)
            if err_code != 0:
                raise Exception(res.get('error_msg'))
            else:
                return res
        except Exception as e:
            self.logger.error('人脸识别错误: %s' % e)
            if self.FACE_MATCH_TIME < self.RETRY_TIME:
                self.FACE_MATCH_TIME += 1
                self.__matchFace()
            else:
                self.logger.error('人脸识别失败，重试次数已用尽，程序退出')
                pag.alert('人脸识别失败，重试次数已用尽，程序退出', title=self.ALERT_TITLE, timeout=self.ALERT_TIMEOUT)
                exit()

    # 拍照
    def __getFace(self):
        cap = cv2.VideoCapture(0)
        while True:
            time.sleep(5)
            ret, frame = cap.read()
            if ret:
                # 制作缩略图
                image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                image.thumbnail((500, 300))
                if not os.path.exists('./picture'):
                    os.mkdir('./picture')
                image.save("./picture/face.jpg", format='jpeg')
                del frame, ret, image
                break
            else:
                self.logger.error('拍照失败，重试...')
                if self.GET_FACE_TIME < self.RETRY_TIME:
                    self.GET_FACE_TIME += 1
                else:
                    self.logger.error('拍照失败，重试次数已用尽，程序退出')
                    pag.alert('拍照失败，重试次数已用尽，程序退出', title=self.ALERT_TITLE, timeout=self.ALERT_TIMEOUT)
                    exit()
        cap.release()

    # 检查鼠标是否移动
    def __checkPointMove(self):
        # 每隔10秒检查一次
        time.sleep(20)
        x, y = pag.position()
        self.logger.info('鼠标坐标：x=%d,y=%d' % (x, y))
        if x == self.POINT_X and y == self.POINT_Y:
            self.logger.info('鼠标没动，还是锁屏状态')
        else:
            # 鼠标移动了，说明锁屏，继续运行
            self.LOCK_SCREEN = False
            self.logger.info('鼠标动了，继续开始识别')

    # 开始执行
    def execute(self):
        while True:
            print(self.ACCESS_TOKEN)
            if self.LOCK_SCREEN:
                self.__checkPointMove()
            else:
                self.__checkIsMe()

    def __del__(self):
        print('已关闭')


if __name__ == '__main__':
    fl = FaceLock()
    print('已开启...')
    fl.execute()
