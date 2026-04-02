import os
import json
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

def save_position_data(position_data):
    """保存位置数据到文件"""
    try:
        config_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_file = os.path.join(config_dir, 'initial_position.json')
        
        with open(config_file, 'w') as f:
            json.dump(position_data, f, indent=4)
        
        print(f"位置数据已保存到: {config_file}")
        return True
    except Exception as e:
        print(f"保存位置数据失败: {str(e)}")
        return False

def load_position_data():
    """从文件加载位置数据"""
    try:
        config_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_file = os.path.join(config_dir, 'initial_position.json')
        
        if not os.path.exists(config_file):
            return None
        
        with open(config_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载位置数据失败: {str(e)}")
        return None

def register_initial_position_tools(mcp):
    """注册初始位置工具"""
    
    @mcp.tool()
    async def save_initial_position(x: float, y: float, zoom: float) -> dict:
        """设置摄像头初始位置信息
        
        功能说明：
        此工具用于将摄像头的当前位置设置为初始位置，并保存到配置文件中。
        
        工作流程：
        1. 接收位置参数（x, y, zoom）
        2. 将位置数据保存到配置文件
        3. 返回操作结果
        
        参数：
        - x: 摄像头的X坐标（水平位置）
        - y: 摄像头的Y坐标（垂直位置）
        - zoom: 摄像头的变焦值
        
        返回值：
        操作结果的JSON对象，包含success、message和position信息
        
        使用场景：
        - 保存重要位置作为初始位置
        - 为后续重置操作提供基准位置
        - 记录摄像头的标准位置
        
        注意事项：
        - 位置数据会覆盖之前保存的初始位置
        - 配置文件保存在项目根目录
        """
        try:
            position = {
                "x": x,
                "y": y,
                "zoom": zoom
            }
            
            if save_position_data(position):
                return {
                    "success": True,
                    "message": f"初始位置已设置: X={x}, Y={y}, Zoom={zoom}",
                    "position": position
                }
            else:
                return {
                    "success": False,
                    "message": "保存初始位置失败"
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"设置初始位置时出现错误: {str(e)}"
            }
    
    @mcp.tool()
    async def get_saved_initial_position() -> dict:
        """获取摄像头初始位置信息
        
        功能说明：
        此工具用于从配置文件中读取已保存的初始位置信息。
        
        工作流程：
        1. 读取配置文件中的位置数据
        2. 返回位置信息
        
        参数：
        无参数
        
        返回值：
        包含初始位置信息的JSON对象，或错误信息
        
        使用场景：
        - 查看已保存的初始位置
        - 验证初始位置是否正确
        - 获取位置信息用于其他操作
        
        注意事项：
        - 如果配置文件不存在，会返回相应错误信息
        - 位置数据包括x、y和zoom三个参数
        """
        try:
            position = load_position_data()
            
            if position:
                return {
                    "success": True,
                    "message": "成功获取初始位置",
                    "position": position
                }
            else:
                return {
                    "success": False,
                    "message": "未找到已保存的初始位置，请先使用save_initial_position工具设置"
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"获取初始位置时出现错误: {str(e)}"
            }
