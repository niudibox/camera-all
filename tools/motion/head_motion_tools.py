#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
摄像头摇头点头控制工具
提供自然语言可调用的摇头和点头功能
"""

import sys
import os
import time

# 添加项目路径到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
from onvif import ONVIFCamera

# 加载环境变量
load_dotenv()

class HeadMotionController:
    """摇头点头控制器"""
    
    def __init__(self):
        """初始化控制器"""
        self.camera = None
        self.ptz = None
        self.media = None
        self.token = None
        self.initial_position = None
        
    def initialize_camera(self):
        """初始化摄像头连接"""
        try:
            from tools.motion.motion_tools import CAMERA_IPS, current_camera_ip_index
            
            # 获取当前摄像头的IP
            ip = CAMERA_IPS[current_camera_ip_index]
            port = os.environ.get('ONVIF_CAMERA_PORT', '8010')
            user = os.environ.get('ONVIF_CAMERA_USERNAME', 'admin')
            password = os.environ.get('ONVIF_CAMERA_PASSWORD')
            
            print(f"连接摄像头: {ip}:{port}")
            
            # 连接摄像头
            self.camera = ONVIFCamera(ip, port, user, password)
            self.ptz = self.camera.create_ptz_service()
            self.media = self.camera.create_media_service()
            
            # 获取token
            profiles = self.media.GetProfiles()
            self.token = profiles[0].token
            
            # 获取初始位置
            self.get_current_position()
            
            print("摄像头初始化成功")
            return True
        except Exception as e:
            print(f"摄像头初始化失败: {e}")
            return False
    
    def get_current_position(self):
        """获取摄像头当前位置"""
        try:
            # 创建获取状态请求
            request = self.ptz.create_type('GetStatus')
            request.ProfileToken = self.token
            
            # 获取状态
            status = self.ptz.GetStatus(request)
            self.initial_position = status.Position
            # 正确访问PanTilt和Zoom属性
            pan = getattr(self.initial_position.PanTilt, 'x', 0) if self.initial_position.PanTilt else 0
            tilt = getattr(self.initial_position.PanTilt, 'y', 0) if self.initial_position.PanTilt else 0
            zoom = getattr(self.initial_position.Zoom, 'x', 0) if self.initial_position.Zoom else 0
            print(f"初始摄像头位置: Pan={pan}, Tilt={tilt}, Zoom={zoom}")
            
            # 不论变焦值是否为0，都执行放大缩小操作来获取最新的变焦数值
            print("执行放大缩小操作以获取最新变焦数值...")
            try:
                # 执行一个极小的放大操作，然后再执行一个同样大小的缩小操作
                # 这样可以获取到真实的变焦值而不改变实际变焦
                small_zoom = 0.001  # 极小的变焦值，几乎不影响视觉效果
                
                # 执行微小放大
                rel_request = self.ptz.create_type('RelativeMove')
                rel_request.ProfileToken = self.token
                rel_request.Translation = {'Zoom': {'x': small_zoom}}
                self.ptz.RelativeMove(rel_request)
                time.sleep(0.1)  # 短暂等待
                
                # 再次获取状态
                status = self.ptz.GetStatus(request)
                updated_zoom = getattr(status.Position.Zoom, 'x', 0) if status.Position.Zoom else 0
                
                # 执行微小缩小，恢复到原始状态
                rel_request.Translation = {'Zoom': {'x': -small_zoom}}
                self.ptz.RelativeMove(rel_request)
                time.sleep(0.1)  # 短暂等待
                
                # 最后再次获取状态
                status = self.ptz.GetStatus(request)
                final_zoom = getattr(status.Position.Zoom, 'x', 0) if status.Position.Zoom else 0
                
                # 更新位置信息
                self.initial_position = status.Position
                zoom = final_zoom
                print(f"获取到最新变焦值: {zoom}")
            except Exception as e:
                print(f"获取最新变焦值时出错: {e}")
            
            return self.initial_position
        except Exception as e:
            print(f"获取摄像头位置失败: {e}")
            return None
    
    def move_to_initial_position(self):
        """将摄像头移回初始位置"""
        if self.initial_position is None:
            print("未获取到初始位置信息")
            return False
            
        try:
            # 创建绝对移动请求
            request = self.ptz.create_type('AbsoluteMove')
            request.ProfileToken = self.token
            request.Position = self.initial_position
            
            # 不设置速度参数，让摄像头使用默认速度
            # 这样可以避免速度参数中的Zoom设置影响变焦
            
            # 执行移动
            self.ptz.AbsoluteMove(request)
            
            # 获取并打印移动后的位置，确认变焦值是否正确
            time.sleep(0.5)  # 等待移动完成
            status_request = self.ptz.create_type('GetStatus')
            status_request.ProfileToken = self.token
            status = self.ptz.GetStatus(status_request)
            
            pan = getattr(status.Position.PanTilt, 'x', 0) if status.Position.PanTilt else 0
            tilt = getattr(status.Position.PanTilt, 'y', 0) if status.Position.PanTilt else 0
            zoom = getattr(status.Position.Zoom, 'x', 0) if status.Position.Zoom else 0
            print(f"已移回初始位置: Pan={pan}, Tilt={tilt}, Zoom={zoom}")
            
            return True
        except Exception as e:
            print(f"移回初始位置失败: {e}")
            return False
    
    def _create_move_request(self, direction, speed):
        """创建移动请求"""
        # 定义各方向参数
        directions = {
            'up':           {'x': 0.0,     'y': speed},
            'down':         {'x': 0.0,     'y': -speed},
            'left':         {'x': -speed,  'y': 0.0},
            'right':        {'x': speed,   'y': 0.0},
            'top-left':     {'x': -speed,  'y': speed},
            'top-right':    {'x': speed,   'y': speed},
            'bottom-left':  {'x': -speed,  'y': -speed},
            'bottom-right': {'x': speed,   'y': -speed}
        }
        
        if direction not in directions:
            raise ValueError(f"无效的方向: {direction}")
        
        # 创建移动请求
        request = self.ptz.create_type('ContinuousMove')
        request.ProfileToken = self.token
        
        # 设置移动速度，不设置Zoom参数，避免影响变焦
        request.Velocity = {'PanTilt': directions[direction]}
        
        return request
    
    def head_shake(self, speed=0.8, duration=0.3):
        """
        摇头动作
        :param speed: 移动速度 (0.1-1.0)
        :param duration: 单向移动时间（秒）
        """
        print(f"执行摇头动作 (速度: {speed}, 单向时间: {duration}秒)")
        
        if not self.initialize_camera():
            return False
            
        try:
            # 创建左右移动请求
            left_request = self._create_move_request('left', speed)
            right_request = self._create_move_request('right', speed)
            
            # 向左移动
            print("向左移动...")
            self.ptz.ContinuousMove(left_request)
            time.sleep(duration)
            
            # 直接切换到向右移动（无停顿）
            print("向右移动...")
            self.ptz.ContinuousMove(right_request)
            time.sleep(duration)
            
            # 停止移动
            self.ptz.Stop({'ProfileToken': self.token})
            
            print("摇头动作完成！")
            return True
            
        except Exception as e:
            print(f"执行过程中出现错误: {e}")
            # 确保停止移动
            try:
                self.ptz.Stop({'ProfileToken': self.token})
            except:
                pass
            return False
    
    def head_nod(self, speed=0.8, duration=0.3):
        """
        点头动作
        :param speed: 移动速度 (0.1-1.0)
        :param duration: 单向移动时间（秒）
        """
        print(f"执行点头动作 (速度: {speed}, 单向时间: {duration}秒)")
        
        if not self.initialize_camera():
            return False
            
        try:
            # 创建上下移动请求
            up_request = self._create_move_request('up', speed)
            down_request = self._create_move_request('down', speed)
            
            # 向上移动
            print("向上移动...")
            self.ptz.ContinuousMove(up_request)
            time.sleep(duration)
            
            # 直接切换到向下移动（无停顿）
            print("向下移动...")
            self.ptz.ContinuousMove(down_request)
            time.sleep(duration)
            
            # 停止移动
            self.ptz.Stop({'ProfileToken': self.token})
            
            print("点头动作完成！")
            return True
            
        except Exception as e:
            print(f"执行过程中出现错误: {e}")
            # 确保停止移动
            try:
                self.ptz.Stop({'ProfileToken': self.token})
            except:
                pass
            return False
    
    def continuous_head_shake(self, speed=0.8, duration=0.3, count=3):
        """
        持续摇头动作（执行指定次数的摇头）
        :param speed: 移动速度 (0.1-1.0)
        :param duration: 单向移动时间（秒）
        :param count: 摇头次数
        """
        print(f"执行持续摇头动作 (速度: {speed}, 单向时间: {duration}秒, 次数: {count})")
        
        if not self.initialize_camera():
            return False
            
        try:
            # 创建左右移动请求
            left_request = self._create_move_request('left', speed)
            right_request = self._create_move_request('right', speed)
            
            # 执行指定次数的摇头
            for i in range(count):
                print(f"第{i+1}次摇头 - 向左移动...")
                self.ptz.ContinuousMove(left_request)
                time.sleep(duration)
                
                print(f"第{i+1}次摇头 - 向右移动...")
                self.ptz.ContinuousMove(right_request)
                time.sleep(duration)
            
            # 停止移动
            self.ptz.Stop({'ProfileToken': self.token})
            
            print("持续摇头动作完成！")
            return True
            
        except Exception as e:
            print(f"执行过程中出现错误: {e}")
            # 确保停止移动
            try:
                self.ptz.Stop({'ProfileToken': self.token})
            except:
                pass
            return False
    
    def continuous_head_nod(self, speed=0.8, duration=0.3, count=3):
        """
        持续点头动作（执行指定次数的点头）
        :param speed: 移动速度 (0.1-1.0)
        :param duration: 单向移动时间（秒）
        :param count: 点头次数
        """
        print(f"执行持续点头动作 (速度: {speed}, 单向时间: {duration}秒, 次数: {count})")
        
        if not self.initialize_camera():
            return False
            
        try:
            # 创建上下移动请求
            up_request = self._create_move_request('up', speed)
            down_request = self._create_move_request('down', speed)
            
            # 执行指定次数的点头
            for i in range(count):
                print(f"第{i+1}次点头 - 向上移动...")
                self.ptz.ContinuousMove(up_request)
                time.sleep(duration)
                
                print(f"第{i+1}次点头 - 向下移动...")
                self.ptz.ContinuousMove(down_request)
                time.sleep(duration)
            
            # 停止移动
            self.ptz.Stop({'ProfileToken': self.token})
            
            print("持续点头动作完成！")
            return True
            
        except Exception as e:
            print(f"执行过程中出现错误: {e}")
            # 确保停止移动
            try:
                self.ptz.Stop({'ProfileToken': self.token})
            except:
                pass
            return False

def register_head_motion_tools(mcp):
    """注册摇头点头工具到MCP系统"""
    
    # 创建控制器实例
    controller = HeadMotionController()
    
    @mcp.tool()
    async def head_shake_tool(speed: float = 0.8, duration: float = 0.3) -> dict:
        """
        控制摄像头执行摇头动作
        参数:
        - speed: 移动速度，范围0.1-1.0，默认0.8
        - duration: 单向移动时间（秒），默认0.3
        
        返回:
        - 操作结果的JSON对象
        """
        try:
            result = controller.head_shake(speed, duration)
            if result:
                return {"success": True, "message": "摇头动作执行成功"}
            else:
                return {"success": False, "message": "摇头动作执行失败"}
        except Exception as e:
            return {"success": False, "message": f"执行摇头动作时出现错误: {str(e)}"}
    
    @mcp.tool()
    async def head_nod_tool(speed: float = 0.8, duration: float = 0.3) -> dict:
        """
        控制摄像头执行点头动作
        参数:
        - speed: 移动速度，范围0.1-1.0，默认0.8
        - duration: 单向移动时间（秒），默认0.3
        
        返回:
        - 操作结果的JSON对象
        """
        try:
            result = controller.head_nod(speed, duration)
            if result:
                return {"success": True, "message": "点头动作执行成功"}
            else:
                return {"success": False, "message": "点头动作执行失败"}
        except Exception as e:
            return {"success": False, "message": f"执行点头动作时出现错误: {str(e)}"}
    
    @mcp.tool()
    async def continuous_head_shake_tool(speed: float = 0.8, duration: float = 0.3, count: int = 3) -> dict:
        """
        控制摄像头执行持续摇头动作（执行指定次数的摇头）
        参数:
        - speed: 移动速度，范围0.1-1.0，默认0.8
        - duration: 单向移动时间（秒），默认0.3
        - count: 摇头次数，默认3次
        
        返回:
        - 操作结果的JSON对象
        """
        try:
            result = controller.continuous_head_shake(speed, duration, count)
            if result:
                return {"success": True, "message": f"持续摇头动作执行成功，执行了{count}次摇头"}
            else:
                return {"success": False, "message": "持续摇头动作执行失败"}
        except Exception as e:
            return {"success": False, "message": f"执行持续摇头动作时出现错误: {str(e)}"}
    
    @mcp.tool()
    async def continuous_head_nod_tool(speed: float = 0.8, duration: float = 0.3, count: int = 3) -> dict:
        """
        控制摄像头执行持续点头动作（执行指定次数的点头）
        参数:
        - speed: 移动速度，范围0.1-1.0，默认0.8
        - duration: 单向移动时间（秒），默认0.3
        - count: 点头次数，默认3次
        
        返回:
        - 操作结果的JSON对象
        """
        try:
            result = controller.continuous_head_nod(speed, duration, count)
            if result:
                return {"success": True, "message": f"持续点头动作执行成功，执行了{count}次点头"}
            else:
                return {"success": False, "message": "持续点头动作执行失败"}
        except Exception as e:
            return {"success": False, "message": f"执行持续点头动作时出现错误: {str(e)}"}
