import time
from typing import Optional
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

def register_preset_tools(mcp: FastMCP):
    """注册预设点管理工具"""
    
    @mcp.tool()
    async def get_position_and_name(question: str = "请结合图片描述生成50字内的图片名称") -> str:
        """获取当前画面坐标与命名
        
        参数：
        - question: AI识别问题，用于生成画面名称
        
        返回值：
        包含名称和坐标信息的文本
        """
        from tools.motion.motion_tools import camera
        if camera is None:
            return "摄像头未初始化，无法使用此功能"
        
        try:
            position_result = camera.get_current_position()
            if not position_result.get("success", False):
                return f"获取位置失败: {position_result.get('error', '未知错误')}"
            
            x = position_result.get("x", 0)
            y = position_result.get("y", 0)
            zoom = position_result.get("zoom", 0)
            coordinates = f"{x}:{y}:{zoom}"
            
            image_result = camera.get_image_data()
            if not image_result.get("success", False):
                return f"获取图像失败: {image_result.get('error', '未知错误')}"
            
            image_data = image_result.get("image_data", b'')
            
            recognize_result = camera.capture_and_recognize(question)
            name = recognize_result.get("result", "未知位置")
            
            return f"名称: {name}, 坐标: {coordinates}"
        except Exception as e:
            return f"工具执行异常: {str(e)}"
    
    @mcp.tool()
    async def add_manual_preset(name: str, coordinates: str) -> str:
        """写入手动预设点
        
        参数：
        - name: 预设点名称
        - coordinates: 坐标，格式为x:y:zoom
        
        返回值：
        操作结果信息
        """
        from tools.motion.motion_tools import camera
        if camera is None:
            return "摄像头未初始化，无法使用此功能"
        
        if not name or not coordinates:
            return "错误: 名称和坐标都是必需的参数"
        
        try:
            parts = coordinates.split(':')
            if len(parts) != 3:
                raise ValueError("坐标格式不正确，应为x:y:zoom")
            
            x = float(parts[0])
            y = float(parts[1])
            zoom = float(parts[2])
            
            move_result = camera.absolute_move(x, y, zoom)
            if not move_result.get("success", False):
                return f"移动到指定位置失败: {move_result.get('error', '未知错误')}"
            
            print(f"等待摄像头移动到位置 ({x}, {y}, {zoom}) 并稳定...")
            time.sleep(5)
            
            image_result = camera.get_image_data(force_refresh=True)
            if not image_result.get("success", False):
                return f"获取图像失败: {image_result.get('error', '未知错误')}"
            
            image_data = image_result.get("image_data", b'')
            
            recognize_result = camera.capture_and_recognize(
                f"请结合图片描述生成50字内的图片名称，用户提供的名称是: {name}"
            )
            
            final_name = recognize_result.get("result", name)
            
            from core.preset_manager import PresetManager
            preset_manager = PresetManager()
            result = preset_manager.add_preset(final_name, x, y, zoom)
            
            if result.get("success", False):
                return f"预设点添加成功: {result.get('message', '')}\nAI识别名称: {final_name}"
            else:
                return f"预设点添加失败: {result.get('message', '未知错误')}"
        except Exception as e:
            return f"工具执行异常: {str(e)}"
    
    @mcp.tool()
    async def get_manual_preset(name: Optional[str] = None) -> str:
        """读取手动预设点
        
        参数：
        - name: 预设点名称（可选）
        
        返回值：
        预设点信息
        """
        from core.preset_manager import PresetManager
        preset_manager = PresetManager()
        
        if name:
            result = preset_manager.get_preset_by_name(name)
            if result.get("success", False):
                preset = result.get("preset", {})
                return f"名称: {preset.get('name', '')}, 坐标: {preset.get('coordinates', '')}"
            else:
                return result.get('message', '未知错误')
        else:
            result = preset_manager.get_all_presets()
            if result.get("success", False):
                presets = result.get("presets", [])
                if not presets:
                    return "没有找到任何预设点"
                
                preset_list = []
                for preset in presets:
                    preset_list.append(f"名称: {preset.get('name', '')}, 坐标: {preset.get('coordinates', '')}")
                
                return "\n".join(preset_list)
            else:
                return result.get('message', '未知错误')
    
    @mcp.tool()
    async def import_system_presets() -> str:
        """系统预设点导入与命名
        
        返回值：
        导入结果统计信息
        """
        from tools.motion.motion_tools import camera
        if camera is None:
            return "摄像头未初始化，无法使用此功能"
        
        try:
            system_presets_result = camera.get_system_presets()
            if not system_presets_result.get("success", False):
                return f"获取系统预设点失败: {system_presets_result.get('error', '未知错误')}"
            
            system_presets = system_presets_result.get("presets", [])
            if not system_presets:
                return "没有找到任何系统预设点"
            
            from core.preset_manager import PresetManager
            preset_manager = PresetManager()
            
            imported_count = 0
            skipped_count = 0
            errors = []
            
            for i, preset in enumerate(system_presets):
                try:
                    preset_name = preset.get("name", "")
                    if not preset_name:
                        errors.append("发现没有名称的系统预设点")
                        skipped_count += 1
                        continue
                    
                    progress = f"正在处理第 {i+1}/{len(system_presets)} 个预设点: {preset_name}"
                    print(progress)
                    
                    move_result = camera.move_to_preset(preset_name)
                    if not move_result.get("success", False):
                        errors.append(f"移动到预设点 '{preset_name}' 失败: {move_result.get('error', '未知错误')}")
                        skipped_count += 1
                        continue
                    
                    print(f"等待摄像头移动到预设点 '{preset_name}' 并稳定...")
                    time.sleep(15)
                    
                    position_result = camera.get_current_position()
                    if not position_result.get("success", False):
                        errors.append(f"获取预设点 '{preset_name}' 位置失败: {position_result.get('error', '未知错误')}")
                        skipped_count += 1
                        continue
                    
                    x = position_result.get("x", 0)
                    y = position_result.get("y", 0)
                    zoom = position_result.get("zoom", 0)
                    
                    image_result = camera.get_image_data()
                    if not image_result.get("success", False):
                        errors.append(f"获取预设点 '{preset_name}' 图像失败: {image_result.get('error', '未知错误')}")
                        skipped_count += 1
                        continue
                    
                    image_data = image_result.get("image_data", b'')
                    
                    recognize_result = camera.capture_and_recognize("请结合图片描述生成50字内的图片名称")
                    name = recognize_result.get("result", preset_name)
                    
                    preset_result = preset_manager.add_preset(name, x, y, zoom)
                    
                    if preset_result.get("success", False):
                        imported_count += 1
                        print(f"成功导入预设点: {name}")
                    else:
                        errors.append(f"添加预设点 '{name}' 失败: {preset_result.get('message', '未知错误')}")
                        skipped_count += 1
                
                except Exception as e:
                    errors.append(f"处理系统预设点时出错: {str(e)}")
                    skipped_count += 1
            
            return f"系统预设点导入完成，成功导入 {imported_count} 个，跳过 {skipped_count} 个\n错误信息:\n" + "\n".join(errors)
        except Exception as e:
            return f"工具执行异常: {str(e)}"
    
    @mcp.tool()
    async def scan_full_view(
        x_step: float = 0.1,
        y_step: float = 0.1,
        zoom: float = 0,
        x_min: float = 0,
        x_max: float = 1,
        y_min: float = -1,
        y_max: float = 1,
        scan_mode: str = "full"
    ) -> str:
        """全视野扫描
        
        参数：
        - x_step: X轴步长
        - y_step: Y轴步长
        - zoom: 变焦值
        - x_min: X轴最小值
        - x_max: X轴最大值
        - y_min: Y轴最小值
        - y_max: Y轴最大值
        - scan_mode: 扫描模式
        
        返回值：
        扫描结果信息
        """
        return "全视野扫描功能暂未实现，请使用其他预设点管理工具"
