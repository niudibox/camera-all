import time
import threading
from typing import Optional
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
import os
import sys
import re

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from core.camera_controller import CameraController

CAMERA_IPS = [
    os.getenv('ONVIF_CAMERA_IP', '192.168.68.216'),
    os.getenv('ONVIF_CAMERA_IP_2', ''),
    os.getenv('ONVIF_CAMERA_IP_3', ''),
    os.getenv('ONVIF_CAMERA_IP_4', '')
]

RTSP_IPS = [
    os.getenv('RTSP_CAMERA_IP', '192.168.68.216'),
    os.getenv('RTSP_CAMERA_IP_2', ''),
    os.getenv('RTSP_CAMERA_IP_3', ''),
    os.getenv('RTSP_CAMERA_IP_4', '')
]

current_camera_ip_index = 0

camera = None
try:
    camera = CameraController(
        CAMERA_IPS[0],
        int(os.getenv('ONVIF_CAMERA_PORT', '8010')),
        os.getenv('ONVIF_CAMERA_USERNAME', 'admin'),
        os.getenv('ONVIF_CAMERA_PASSWORD'),
        os.getenv('CAMERA_MEDIA_PROFILE_TOKEN', 'profile_1'),
        RTSP_IPS[0]
    )
    print("摄像头初始化成功")
except Exception as e:
    print(f"摄像头初始化失败: {e}")

DEFAULT_CAMERA_SPEED = float(os.getenv('DEFAULT_CAMERA_SPEED', '0.5'))
MAX_CAMERA_SPEED = float(os.getenv('MAX_CAMERA_SPEED', '1.0'))
MIN_CAMERA_SPEED = float(os.getenv('MIN_CAMERA_SPEED', '0.1'))
CONTINUOUS_MOVE_DURATION = float(os.getenv('CONTINUOUS_MOVE_DURATION', '3'))
SHORT_MOVE_DURATION = float(os.getenv('SHORT_MOVE_DURATION', '1'))
SHORT_ZOOM_DURATION = float(os.getenv('SHORT_ZOOM_DURATION', '1'))
CONTINUOUS_ZOOM_DURATION = float(os.getenv('CONTINUOUS_ZOOM_DURATION', '3'))
CRUISE_PRESET_COUNT = int(os.getenv('CRUISE_PRESET_COUNT', '10'))
CRUISE_PRESET_INTERVAL = int(os.getenv('CRUISE_PRESET_INTERVAL', '15'))

cruise_running = False
cruise_thread = None
cruise_stop_event = threading.Event()

COMMAND_MAP = {
    "上": ('move', 'up', False),
    "下": ('move', 'down', False),
    "左": ('move', 'left', False),
    "右": ('move', 'right', False),
    "一直上": ('move', 'up', True),
    "一直下": ('move', 'down', True),
    "一直左": ('move', 'left', True),
    "一直右": ('move', 'right', True),
    "放大": ('zoom', 'in', False),
    "缩小": ('zoom', 'out', False),
    "一直放大": ('zoom', 'in', True),
    "一直缩小": ('zoom', 'out', True),
}

PRESET_COMMANDS = {f"预设点{i}": i for i in range(1, 11)}

def execute_ptz_command(command: str):
    """执行 PTZ 控制命令"""
    if camera is None:
        return {"success": False, "error": "摄像头未初始化"}
    
    if command in COMMAND_MAP:
        cmd_type, direction, is_continuous = COMMAND_MAP[command]
        
        if cmd_type == 'move':
            duration = CONTINUOUS_MOVE_DURATION if is_continuous else SHORT_MOVE_DURATION
            x_move = 0
            y_move = 0
            
            if direction == 'left':
                x_move = -DEFAULT_CAMERA_SPEED
            elif direction == 'right':
                x_move = DEFAULT_CAMERA_SPEED
            elif direction == 'up':
                y_move = DEFAULT_CAMERA_SPEED
            elif direction == 'down':
                y_move = -DEFAULT_CAMERA_SPEED
            
            result = camera.continuous_move(x_move, y_move, duration)
            return result
        
        elif cmd_type == 'zoom':
            duration = CONTINUOUS_ZOOM_DURATION if is_continuous else SHORT_ZOOM_DURATION
            zoom_direction = 'in' if direction == 'in' else 'out'
            result = camera.relative_zoom(zoom_direction, duration)
            return result
    
    elif command in PRESET_COMMANDS:
        preset_number = PRESET_COMMANDS[command]
        presets_result = camera.get_system_presets()
        if not presets_result.get("success") or not presets_result.get("presets"):
            return {"success": False, "error": "没有找到预设点"}
        
        all_presets = presets_result["presets"]
        if preset_number < 1 or preset_number > len(all_presets):
            return {"success": False, "error": f"预设点编号 {preset_number} 超出范围 (1-{len(all_presets)})"}
        
        target_preset = all_presets[preset_number - 1]
        result = camera.move_to_preset(target_preset["name"])
        return result
    
    elif command == "一键巡航":
        return start_cruise()
    
    elif command == "停止巡航":
        return stop_cruise()
    
    elif command in ["控制切换1", "控制切换2", "控制切换3", "控制切换4"]:
        index = int(command[-1]) - 1
        return switch_camera(index)
    
    return {"success": False, "error": f"未知指令: {command}"}

def cruise_loop():
    """巡航循环线程函数"""
    global cruise_running
    
    if camera is None:
        print("摄像头控制器未初始化，无法执行巡航")
        cruise_running = False
        return
    
    try:
        presets_result = camera.get_system_presets()
        if not presets_result.get("success") or not presets_result.get("presets"):
            print("没有找到预设点，无法执行巡航")
            cruise_running = False
            return
        
        all_presets = presets_result["presets"]
        presets = all_presets[:CRUISE_PRESET_COUNT]
        
        print(f"找到 {len(all_presets)} 个预设点，将巡航前 {len(presets)} 个预设点")
        print(f"预设点间隔: {CRUISE_PRESET_INTERVAL} 秒")
        
        cycle_count = 0
        while cruise_running and not cruise_stop_event.is_set():
            cycle_count += 1
            print(f"开始第 {cycle_count} 轮巡航")
            
            for i, preset in enumerate(presets):
                if cruise_stop_event.is_set():
                    print("收到停止信号，中断巡航")
                    break
                
                print(f"移动到预设点 {i+1}/{len(presets)}: {preset['name']}")
                result = camera.move_to_preset(preset["name"])
                
                if not result.get("success"):
                    print(f"移动失败: {result.get('error')}")
                
                if i < len(presets) - 1 or cruise_running:
                    for _ in range(CRUISE_PRESET_INTERVAL):
                        if cruise_stop_event.is_set():
                            break
                        time.sleep(1)
            
            if cruise_stop_event.is_set():
                break
            
            print(f"完成第 {cycle_count} 轮")
        
        print(f"巡航已停止，共执行 {cycle_count} 轮")
        
    except Exception as e:
        print(f"巡航执行失败: {e}")
    finally:
        cruise_running = False

def start_cruise():
    """启动巡航"""
    global cruise_running, cruise_thread
    
    if camera is None:
        return {"success": False, "error": "摄像头未初始化"}
    
    if cruise_running:
        return {"success": False, "error": "巡航已在运行中"}
    
    try:
        cruise_stop_event.clear()
        cruise_running = True
        cruise_thread = threading.Thread(target=cruise_loop, daemon=True)
        cruise_thread.start()
        return {"success": True, "message": "已开始巡航"}
    except Exception as e:
        cruise_running = False
        return {"success": False, "error": str(e)}

def stop_cruise():
    """停止巡航"""
    global cruise_running
    
    if not cruise_running:
        return {"success": False, "error": "巡航未在运行"}
    
    try:
        cruise_stop_event.set()
        cruise_running = False
        if cruise_thread and cruise_thread.is_alive():
            cruise_thread.join(timeout=5)
        return {"success": True, "message": "已停止巡航"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def switch_camera(target_index):
    """切换摄像头IP地址"""
    global camera, current_camera_ip_index
    
    if target_index < 0 or target_index >= len(CAMERA_IPS):
        return {"success": False, "error": f"无效的摄像头索引: {target_index}"}
    
    if not CAMERA_IPS[target_index]:
        return {"success": False, "error": f"摄像头IP {target_index + 1} 未配置"}
    
    if cruise_running:
        stop_cruise()
    
    new_ip = CAMERA_IPS[target_index]
    new_rtsp_ip = RTSP_IPS[target_index] or new_ip
    
    try:
        if camera:
            camera.stop_video_stream()
    except Exception as e:
        print(f"关闭视频流失败: {e}")
    
    try:
        camera = CameraController(
            new_ip,
            int(os.getenv('ONVIF_CAMERA_PORT', '8010')),
            os.getenv('ONVIF_CAMERA_USERNAME', 'admin'),
            os.getenv('ONVIF_CAMERA_PASSWORD'),
            os.getenv('CAMERA_MEDIA_PROFILE_TOKEN', 'profile_1'),
            new_rtsp_ip
        )
        current_camera_ip_index = target_index
        print(f"摄像头IP切换成功: {new_ip} (RTSP: {new_rtsp_ip})")
        return {"success": True, "message": f"已切换到摄像头{target_index + 1}: {new_ip}"}
    except Exception as e:
        return {"success": False, "error": f"切换失败: {str(e)}"}

def register_motion_tools(mcp: FastMCP):
    """注册云台控制工具"""
    
    @mcp.tool()
    async def EyeCam(question: str = "请描述这张图片的内容") -> dict:
        """摄像头视觉识别功能
        
        参数：
        - question: 你想问的关于照片的问题，默认为"请描述这张图片的内容"
        
        返回值：
        提供照片信息的JSON对象
        """
        if camera is None:
            return {"success": False, "result": "摄像头未初始化，无法使用视觉识别功能"}
        
        try:
            result = camera.capture_and_recognize(question)
            print(f"视觉识别结果: {result}")
            return result
        except Exception as e:
            print(f"Error in EyeCam: {e}")
            return {"success": False, "result": str(e)}
    
    if os.getenv('ONVIF_CAMERA_PTZ_ENABLED') == 'true':
        @mcp.tool()
        async def ptz_control(command: str) -> dict:
            """PTZ控制指令
            
            支持以下指令：
            方向控制（8个）：上、下、左、右、一直上、一直下、一直左、一直右
            变焦控制（4个）：放大、缩小、一直放大、一直缩小
            巡航控制（2个）：一键巡航、停止巡航
            摄像头切换（4个）：控制切换1、控制切换2、控制切换3、控制切换4
            预设点控制（10个）：预设点1-预设点10
            
            参数：
            - command: 控制指令
            
            返回值：
            操作结果的JSON对象
            """
            if camera is None:
                return {"success": False, "error": "摄像头未初始化，无法使用云台控制功能"}
            
            try:
                result = execute_ptz_command(command)
                print(f"PTZ控制指令执行结果: {result}")
                return result
            except Exception as e:
                print(f"Error in ptz_control: {e}")
                return {"success": False, "error": str(e)}
        
        @mcp.tool()
        async def move_camera(direction: str, speed: float = DEFAULT_CAMERA_SPEED) -> dict:
            """控制摄像头向指定方向移动
            
            参数：
            - direction: 移动方向，可选值："up", "down", "left", "right"
            - speed: 移动速度，默认0.5，范围在0.1到1.0之间
            
            返回值：
            操作结果的JSON对象
            """
            speed = max(MIN_CAMERA_SPEED, min(MAX_CAMERA_SPEED, speed))
            
            if camera is None:
                return {"success": False, "result": "摄像头未初始化，无法使用云台控制功能"}
            
            try:
                result = camera.continuous_move(
                    1.0 if direction == 'right' else -1.0 if direction == 'left' else 0,
                    -1.0 if direction == 'down' else 1.0 if direction == 'up' else 0,
                    SHORT_MOVE_DURATION
                )
                print(f"移动摄像头结果: {result}")
                return {"success": True, "result": f"已向{direction}移动"}
            except Exception as e:
                print(f"Error in move_camera: {e}")
                return {"success": False, "result": str(e)}
        
        @mcp.tool()
        async def clear_obstruction_tool(speed: float = DEFAULT_CAMERA_SPEED) -> dict:
            """控制摄像头向上移动以开启视线遮挡
            
            参数：
            - speed: 移动速度，默认0.5，范围在0.1到1.0之间
            
            返回值：
            操作结果的JSON对象
            """
            speed = max(MIN_CAMERA_SPEED, min(MAX_CAMERA_SPEED, speed))
            
            if camera is None:
                return {"success": False, "result": "摄像头未初始化，无法使用云台控制功能"}
            
            try:
                result = camera.continuous_move(0, 1.0, 4.0)
                print(f"开启遮挡结果: {result}")
                return {"success": True, "result": "已向上移动清除遮挡"}
            except Exception as e:
                print(f"Error in clear_obstruction: {e}")
                return {"success": False, "result": str(e)}
        
        @mcp.tool()
        async def start_cruise_tool() -> dict:
            """启动巡航功能
            
            返回值：
            操作结果的JSON对象
            """
            return start_cruise()
        
        @mcp.tool()
        async def stop_cruise_tool() -> dict:
            """停止巡航功能
            
            返回值：
            操作结果的JSON对象
            """
            return stop_cruise()
        
        @mcp.tool()
        async def switch_camera_tool(camera_index: int) -> dict:
            """切换摄像头
            
            参数：
            - camera_index: 摄像头索引 (1-4)
            
            返回值：
            操作结果的JSON对象
            """
            return switch_camera(camera_index - 1)
        
        @mcp.tool()
        async def natural_language_camera_control(command: str) -> dict:
            """通过自然语言控制摄像头移动
            
            参数：
            - command: 自然语言指令
            
            返回值：
            操作结果的JSON对象
            """
            return execute_ptz_command(command)
        
        @mcp.tool()
        async def reset_camera_position() -> dict:
            """重置摄像头位置到初始状态
            
            返回值：
            操作结果的JSON对象
            """
            if camera is None:
                return {"success": False, "result": "摄像头未初始化，无法使用云台控制功能"}
            
            try:
                result = camera.reset_position()
                print(f"重置摄像头位置结果: {result}")
                return {"success": True, "result": "摄像头位置已重置"}
            except Exception as e:
                print(f"Error in reset_camera_position: {e}")
                return {"success": False, "result": str(e)}
    
    @mcp.tool()
    async def move_camera_to_position(x: float, y: float, zoom: float = 0.0) -> dict:
        """将摄像头移动到指定的坐标位置
        
        参数：
        - x: 摄像头的X坐标（水平位置）
        - y: 摄像头的Y坐标（垂直位置）
        - zoom: 摄像头的变焦值（默认为0.0）
        
        返回值：
        操作结果的JSON对象
        """
        if camera is None:
            return {"success": False, "message": "摄像头未初始化，无法使用移动功能"}
        
        try:
            result = camera.absolute_move(x, y, zoom)
            print(f"移动摄像头到位置结果: {result}")
            return {"success": True, "message": f"已移动到位置 ({x}, {y}, {zoom})"}
        except Exception as e:
            print(f"Error in move_camera_to_position: {e}")
            return {"success": False, "message": str(e)}
    
    @mcp.tool()
    async def get_current_position() -> dict:
        """获取摄像头当前位置
        
        返回值：
        包含x, y, zoom坐标的JSON对象
        """
        if camera is None:
            return {"success": False, "message": "摄像头未初始化，无法获取位置"}
        
        try:
            result = camera.get_current_position()
            print(f"获取当前位置结果: {result}")
            return result
        except Exception as e:
            print(f"Error in get_current_position: {e}")
            return {"success": False, "message": str(e)}
    
    @mcp.tool()
    async def get_system_presets_tool() -> dict:
        """获取系统预设点列表
        
        返回值：
        包含预设点列表的JSON对象
        """
        if camera is None:
            return {"success": False, "message": "摄像头未初始化，无法获取预设点"}
        
        try:
            result = camera.get_system_presets()
            print(f"获取系统预设点结果: {result}")
            return result
        except Exception as e:
            print(f"Error in get_system_presets: {e}")
            return {"success": False, "message": str(e)}
    
    @mcp.tool()
    async def move_to_preset_tool(preset_name: str) -> dict:
        """移动到指定预设点
        
        参数：
        - preset_name: 预设点名称
        
        返回值：
        操作结果的JSON对象
        """
        if camera is None:
            return {"success": False, "message": "摄像头未初始化，无法移动到预设点"}
        
        try:
            result = camera.move_to_preset(preset_name)
            print(f"移动到预设点结果: {result}")
            return result
        except Exception as e:
            print(f"Error in move_to_preset: {e}")
            return {"success": False, "message": str(e)}
