import cv2
import requests
import time
import os
import datetime
import threading
import json
import socket
import numpy as np
from typing import Dict, List, Optional, Tuple
from onvif import ONVIFCamera
from getmac import get_mac_address
from dotenv import load_dotenv

load_dotenv()

class CameraController:
    """合并后的摄像头控制器，整合了 Camera 和 OnvifController 的功能"""
    
    def __init__(self, ip: str, port: int, username: str, password: str, media_profile_token: str = None, rtsp_ip: str = None):
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.media_profile_token = media_profile_token
        self.rtsp_ip = rtsp_ip or ip
        
        self.mac_address = get_mac_address()
        self.captures_dir = os.getenv('CAPTURES_DIR', './captures')
        self._ensure_captures_dir_exists()
        
        self.camera = None
        self.ptz_service = None
        self.media_service = None
        self.token = None
        self.videoCapture = None
        self._stream_active = False
        self._stream_thread = None
        self._latest_frame = None
        self._frame_lock = threading.Lock()
        self._last_preset_token = None
        
        self._connect()
        
        # 初始化时立即启动视频流，避免第一次调用没有帧
        try:
            self.start_video_stream()
        except Exception as e:
            print(f"初始化视频流失败: {e}")
    
    def _ensure_captures_dir_exists(self):
        if not os.path.exists(self.captures_dir):
            os.makedirs(self.captures_dir)
    
    def _resolve_address(self, hostname: str) -> str:
        """解析主机名，支持 IPv4 和 IPv6 双栈解析
        
        Args:
            hostname: 主机名或IP地址
            
        Returns:
            解析后的IP地址（优先返回IPv4，如果只有IPv6则返回IPv6）
        """
        try:
            addrinfo = socket.getaddrinfo(hostname, None)
            ipv4_addrs = [addr[4][0] for addr in addrinfo if addr[0] == socket.AF_INET]
            ipv6_addrs = [addr[4][0] for addr in addrinfo if addr[0] == socket.AF_INET6]
            
            if ipv4_addrs:
                return ipv4_addrs[0]
            elif ipv6_addrs:
                return ipv6_addrs[0]
            else:
                return hostname
        except Exception as e:
            print(f"地址解析失败: {hostname}, 错误: {e}")
            return hostname
    
    def _format_rtsp_url(self, ip: str, port: int, user: str, password: str, path: str, params: str = None) -> str:
        """格式化 RTSP URL，支持 IPv4 和 IPv6
        
        Args:
            ip: IP地址
            port: 端口
            user: 用户名
            password: 密码
            path: 路径
            params: 查询参数
            
        Returns:
            格式化后的 RTSP URL
        """
        try:
            addrinfo = socket.getaddrinfo(ip, None)
            is_ipv6 = any(addr[0] == socket.AF_INET6 for addr in addrinfo)
        except:
            is_ipv6 = ':' in ip and '[' not in ip
        
        if is_ipv6:
            formatted_ip = f"[{ip}]"
        else:
            formatted_ip = ip
        
        if params:
            return f"rtsp://{user}:{password}@{formatted_ip}:{port}{path}?{params}"
        else:
            return f"rtsp://{user}:{password}@{formatted_ip}:{port}{path}"
    
    def _connect(self):
        try:
            resolved_ip = self._resolve_address(self.ip)
            
            # ONVIF 库对 IPv6 地址需要特殊处理
            onvif_host = resolved_ip
            try:
                addrinfo = socket.getaddrinfo(resolved_ip, None)
                is_ipv6 = any(addr[0] == socket.AF_INET6 for addr in addrinfo)
            except:
                is_ipv6 = ':' in resolved_ip and '[' not in resolved_ip
            
            if is_ipv6:
                onvif_host = f"[{resolved_ip}]"
            
            self.camera = ONVIFCamera(onvif_host, self.port, self.username, self.password)
            self.ptz_service = self.camera.create_ptz_service()
            self.media_service = self.camera.create_media_service()
            
            profiles = self.media_service.GetProfiles()
            if not profiles or len(profiles) == 0:
                raise Exception("无法获取摄像头配置文件，请检查摄像头连接")
            
            if self.media_profile_token:
                for profile in profiles:
                    if str(profile.token) == self.media_profile_token:
                        self.token = str(profile.token)
                        break
                if not self.token:
                    print(f"警告: 指定的媒体配置文件令牌 {self.media_profile_token} 不存在，使用默认配置文件")
                    self.token = str(profiles[0].token)
            else:
                self.token = str(profiles[0].token)
            
            print(f"成功连接到摄像头 {self.ip}:{self.port} (解析为: {resolved_ip}, ONVIF: {onvif_host})")
            
        except Exception as e:
            raise Exception(f"连接摄像头失败: {str(e)}")
    
    def get_current_position(self, wait_seconds: float = 0.5, delete_preset: bool = False) -> Dict[str, any]:
        try:
            self._write_current_position_to_preset()
            time.sleep(wait_seconds)
            parameters = self._read_preset_parameters()
            if delete_preset:
                self._clear_preset()
            return {"success": True, "x": parameters.get("x", 0), "y": parameters.get("y", 0), "zoom": parameters.get("zoom", 0)}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _write_current_position_to_preset(self) -> bool:
        try:
            if not self._last_preset_token:
                presets = self.ptz_service.GetPresets({'ProfileToken': self.token})
                if presets and len(presets) > 0:
                    self._last_preset_token = str(presets[-1].token)
                else:
                    self._last_preset_token = "14"
            
            preset = self.ptz_service.SetPreset({'ProfileToken': self.token, 'PresetToken': self._last_preset_token})
            return preset is not None
        except Exception as e:
            print(f"写入预设点失败: {e}")
            return False
    
    def _read_preset_parameters(self, wait_seconds: float = 0.5) -> Dict[str, float]:
        time.sleep(wait_seconds)
        preset = self.ptz_service.GetPresets({'ProfileToken': self.token})
        if preset and len(preset) > 0:
            last_preset = preset[-1]
            pan_tilt = last_preset.PTZPosition.PanTilt
            zoom = last_preset.PTZPosition.Zoom
            x = getattr(pan_tilt, 'x', getattr(pan_tilt, '_x', 0))
            y = getattr(pan_tilt, 'y', getattr(pan_tilt, '_y', 0))
            z = getattr(zoom, 'x', getattr(zoom, '_x', 0))
            return {"x": float(x), "y": float(y), "zoom": float(z)}
        return {"x": 0, "y": 0, "zoom": 0}
    
    def _clear_preset(self):
        try:
            if self._last_preset_token:
                self.ptz_service.RemovePreset(self.token, self._last_preset_token)
        except Exception as e:
            print(f"清除预设点失败: {e}")
    
    def get_system_presets(self) -> Dict[str, any]:
        try:
            presets = self.ptz_service.GetPresets({'ProfileToken': self.token})
            if not presets:
                return {"success": False, "presets": [], "error": "没有找到系统预设点"}
            
            preset_list = []
            for preset in presets:
                preset_list.append({
                    "name": preset.Name,
                    "token": str(preset.token)
                })
            
            return {"success": True, "presets": preset_list}
        except Exception as e:
            return {"success": False, "presets": [], "error": str(e)}
    
    def absolute_move(self, x: float, y: float, zoom: float = 0.0) -> Dict[str, any]:
        try:
            request = self.ptz_service.create_type('AbsoluteMove')
            request.ProfileToken = self.token
            request.Position = {
                'PanTilt': {
                    'x': x,
                    'y': y
                },
                'Zoom': {
                    'x': zoom
                }
            }
            
            self.ptz_service.AbsoluteMove(request)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def move_to_preset(self, preset_name: str) -> Dict[str, any]:
        try:
            presets = self.ptz_service.GetPresets({'ProfileToken': self.token})
            target_preset = None
            for preset in presets:
                if preset.Name == preset_name:
                    target_preset = preset
                    break
            
            if not target_preset:
                return {"success": False, "error": f"未找到预设点: {preset_name}"}
            
            self.ptz_service.GotoPreset({'ProfileToken': self.token, 'PresetToken': str(target_preset.token)})
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def continuous_move(self, x: float, y: float, timeout: float = 1.0) -> Dict[str, any]:
        try:
            request = self.ptz_service.create_type('ContinuousMove')
            request.ProfileToken = self.token
            
            request.Velocity = {
                'PanTilt': {
                    'x': x,
                    'y': y
                },
                'Zoom': {
                    'x': 0.0
                }
            }
            
            self.ptz_service.ContinuousMove(request)
            time.sleep(timeout)
            
            stop_request = self.ptz_service.create_type('Stop')
            stop_request.ProfileToken = self.token
            stop_request.PanTilt = True
            stop_request.Zoom = True
            self.ptz_service.Stop(stop_request)
            
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def absolute_zoom(self, zoom_level: float) -> Dict[str, str]:
        try:
            request = self.ptz_service.create_type('AbsoluteMove')
            request.ProfileToken = self.token
            request.Position = {
                'PanTilt': {
                    'x': 0.0,
                    'y': 0.0
                },
                'Zoom': {
                    'x': zoom_level
                }
            }
            
            self.ptz_service.AbsoluteMove(request)
            return {"success": True, "message": f"变焦已设置为 {zoom_level}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def relative_zoom(self, zoom_direction: str, duration: float = 1.0) -> Dict[str, str]:
        try:
            request = self.ptz_service.create_type('ContinuousMove')
            request.ProfileToken = self.token
            
            zoom_speed = 0.5 if zoom_direction == 'in' else -0.5
            
            request.Velocity = {
                'PanTilt': {
                    'x': 0.0,
                    'y': 0.0
                },
                'Zoom': {
                    'x': zoom_speed
                }
            }
            
            self.ptz_service.ContinuousMove(request)
            time.sleep(duration)
            
            stop_request = self.ptz_service.create_type('Stop')
            stop_request.ProfileToken = self.token
            stop_request.PanTilt = True
            stop_request.Zoom = True
            self.ptz_service.Stop(stop_request)
            
            return {"success": True, "message": f"变焦已{zoom_direction}，持续{duration}秒"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def reset_position(self):
        try:
            request = self.ptz_service.create_type('AbsoluteMove')
            request.ProfileToken = self.token
            request.Position = {
                'PanTilt': {
                    'x': 0.0,
                    'y': 0.0
                },
                'Zoom': {
                    'x': 0.0
                }
            }
            
            self.ptz_service.AbsoluteMove(request)
            return {"success": True, "message": "位置已重置"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def start_video_stream(self):
        rtsp_ip = self.rtsp_ip
        rtsp_port = int(os.getenv('RTSP_CAMERA_PORT', '554'))
        rtsp_user = self.username
        rtsp_password = self.password
        rtsp_path = os.getenv('RTSP_CAMERA_PATH', '/Streaming/Channels/101')
        rtsp_params = os.getenv('RTSP_CAMERA_PARAMS', 'transportmode=unicast&profile=Profile_1')
        
        self.rtsp_url = self._format_rtsp_url(rtsp_ip, rtsp_port, rtsp_user, rtsp_password, rtsp_path, rtsp_params)
        
        self.videoCapture = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
        self.videoCapture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.videoCapture.set(cv2.CAP_PROP_FPS, 30)
        self.videoCapture.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
        self.videoCapture.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
        self.videoCapture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('H', '2', '6', '4'))
        
        if not self.videoCapture.isOpened():
            self.videoCapture = cv2.VideoCapture(self.rtsp_url)
            if not self.videoCapture.isOpened():
                raise Exception(f"无法打开视频流：{self.rtsp_url}")
        
        for i in range(5):
            ret, _ = self.videoCapture.read()
            if not ret:
                if i == 4:
                    raise Exception("无法读取视频流的第一帧")
                time.sleep(0.1)
        
        self._stream_active = True
        self._stream_thread = threading.Thread(target=self._stream_worker, daemon=True)
        self._stream_thread.start()
    
    def stop_video_stream(self):
        self._stream_active = False
        if self._stream_thread:
            self._stream_thread.join()
        if self.videoCapture and self.videoCapture.isOpened():
            self.videoCapture.release()
            self.videoCapture = None
        self._latest_frame = None
    
    def _stream_worker(self):
        while self._stream_active:
            ret, frame = self.videoCapture.read()
            if ret:
                with self._frame_lock:
                    self._latest_frame = frame
            else:
                time.sleep(0.01)
    
    def get_current_frame(self, force_refresh: bool = True) -> Dict[str, any]:
        if not self._stream_active:
            self.start_video_stream()
        
        with self._frame_lock:
            if self._latest_frame is not None:
                return {"success": True, "frame": self._latest_frame}
        
        return {"success": False, "error": "无法获取当前帧"}
    
    def get_image_data(self, target_size_kb: int = 50, force_refresh: bool = True) -> Dict[str, any]:
        try:
            frame_result = self.get_current_frame(force_refresh)
            if not frame_result.get("success", False):
                return {"success": False, "error": frame_result.get("error", "未知错误")}
            
            frame = frame_result.get("frame")
            if frame is None:
                return {"success": False, "error": "无法获取图像数据"}
            
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85]
            result, encoded_img = cv2.imencode('.jpg', frame, encode_param)
            
            if not result:
                return {"success": False, "error": "图像编码失败"}
            
            img_bytes = encoded_img.tobytes()
            img_size_kb = len(img_bytes) / 1024
            
            if img_size_kb > target_size_kb:
                scale_factor = (target_size_kb / img_size_kb) ** 0.5
                new_width = int(frame.shape[1] * scale_factor)
                new_height = int(frame.shape[0] * scale_factor)
                resized_frame = cv2.resize(frame, (new_width, new_height))
                result, encoded_img = cv2.imencode('.jpg', resized_frame, encode_param)
                if result:
                    img_bytes = encoded_img.tobytes()
            
            if os.environ.get('ONVIF_CAMERA_CAPTURE') == 'true':
                timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                img_name = f'capture_{timestamp}.jpg'
                img_path = os.path.join(self.captures_dir, img_name)
                with open(img_path, 'wb') as f:
                    f.write(img_bytes)
            
            return {"success": True, "image_data": img_bytes}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def capture_and_recognize(self, question: str) -> dict:
        try:
            image_result = self.get_image_data()
            if not image_result.get("success", False):
                return {"success": False, "error": f"获取图像失败: {image_result.get('error', '未知错误')}"}
            
            image_data = image_result.get("image_data", b'')
            
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%m%S')
            img_name = f'img_{timestamp}.jpg'
            
            self._ensure_captures_dir_exists()
            
            if os.environ.get('ONVIF_CAMERA_CAPTURE') == 'true':
                img_path = os.path.join(self.captures_dir, img_name)
                with open(img_path, 'wb') as f:
                    f.write(image_data)
            
            api_url = os.getenv('AI_API_URL', 'https://api.xiaozhi.me/vision/explain')
            api_token = os.getenv('AI_API_TOKEN', 'test-token')
            timeout = int(os.getenv('AI_TIMEOUT', '15'))
            
            files = {'file': (img_name, image_data, 'image/jpeg')}
            data = {'question': question}
            headers = {
                'Authorization': f'Bearer {api_token}',
                'Device-Id': self.mac_address,
                'Client-Id': self.mac_address
            }
            
            response = requests.post(api_url, files=files, data=data, headers=headers, timeout=timeout)
            response.raise_for_status()
            result = response.json()
            
            self._ensure_captures_dir_exists()
            
            if os.environ.get('ONVIF_CAMERA_LOG') == 'true':
                log_path = os.path.join(self.captures_dir, 'log.txt')
                if not os.path.exists(log_path):
                    with open(log_path, 'w', encoding='utf-8') as log_file:
                        log_file.write("")
                with open(log_path, 'r+', encoding='utf-8') as log_file:
                    content = log_file.read()
                    log_file.seek(0, 0)
                    log_file.write(f"识别时间: {timestamp}\n")
                    log_file.write(f"图片名称: {img_name}\n")
                    log_file.write(f"问题描述: {question}\n")
                    log_file.write(f"识别结果: {result.get('text', '无法识别')}\n")
                    log_file.write("------------------------------------------------------------\n")
                    log_file.write(content)
            
            return result
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            
            self._ensure_captures_dir_exists()
            
            log_path = os.path.join(self.captures_dir, 'log.txt')
            with open(log_path, 'a', encoding='utf-8') as log_file:
                log_file.write(f"识别时间: {timestamp}\n")
                log_file.write(f"问题描述: {question}\n")
                log_file.write(f"图片名称: {img_name}\n")
                log_file.write(f"错误信息: {error_msg}\n")
                log_file.write("--------------------\n")
            
            return {"success": False, "result": error_msg}
        except Exception as e:
            return {"success": False, "result": str(e)}
