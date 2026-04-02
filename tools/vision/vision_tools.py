from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

def register_vision_tools(mcp: FastMCP):
    """注册视觉识别工具"""
    
    @mcp.tool()
    async def capture_image(question: str = "请描述这张图片的内容") -> dict:
        """捕获当前画面并进行AI识别
        
        参数：
        - question: AI识别问题，默认为"请描述这张图片的内容"
        
        返回值：
        包含识别结果的JSON对象
        """
        from tools.motion.motion_tools import camera
        if camera is None:
            return {"success": False, "result": "摄像头未初始化，无法使用视觉识别功能"}
        
        try:
            result = camera.capture_and_recognize(question)
            print(f"视觉识别结果: {result}")
            return result
        except Exception as e:
            print(f"Error in capture_image: {e}")
            return {"success": False, "result": str(e)}
    
    @mcp.tool()
    async def get_latest_frame() -> dict:
        """获取最新的视频帧
        
        返回值：
        包含帧数据的JSON对象
        """
        from tools.motion.motion_tools import camera
        if camera is None:
            return {"success": False, "message": "摄像头未初始化，无法获取视频帧"}
        
        try:
            result = camera.get_current_frame()
            print(f"获取最新帧结果: {result}")
            return result
        except Exception as e:
            print(f"Error in get_latest_frame: {e}")
            return {"success": False, "message": str(e)}
