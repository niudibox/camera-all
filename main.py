#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Camera All - 统一的摄像头 MCP 服务器
整合了 camera-tools 和 cameras 项目的所有功能
"""

from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
import os
import sys

load_dotenv()

# 创建 MCP 服务器
mcp = FastMCP("CameraAll")

# 添加核心模块路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 注册所有工具模块
from tools.preset.preset_tools import register_preset_tools
from tools.motion.motion_tools import register_motion_tools
from tools.motion.initial_position_tools import register_initial_position_tools
from tools.motion.head_motion_tools import register_head_motion_tools

# 注册预设点管理工具（5个）
register_preset_tools(mcp)

# 注册云台控制工具（13个，包含视觉识别）
register_motion_tools(mcp)

# 注册初始位置工具（2个）
register_initial_position_tools(mcp)

# 注册摇头点头工具（4个）
register_head_motion_tools(mcp)

def main():
    """主函数"""
    print("=" * 50)
    print("Camera All MCP Server 已启动")
    print("=" * 50)
    print("已注册的工具分类:")
    print("- 预设点管理: 5 个工具")
    print("  * get_position_and_name")
    print("  * add_manual_preset")
    print("  * get_manual_preset")
    print("  * import_system_presets")
    print("  * scan_full_view")
    print("- 云台控制: 13 个工具")
    print("  * EyeCam (视觉识别)")
    print("  * ptz_control (PTZ控制指令，30种指令)")
    print("  * move_camera")
    print("  * clear_obstruction_tool")
    print("  * start_cruise_tool")
    print("  * stop_cruise_tool")
    print("  * switch_camera_tool")
    print("  * natural_language_camera_control")
    print("  * reset_camera_position")
    print("  * move_camera_to_position")
    print("  * get_current_position")
    print("  * get_system_presets_tool")
    print("  * move_to_preset_tool")
    print("- 初始位置: 2 个工具")
    print("  * save_initial_position")
    print("  * get_saved_initial_position")
    print("- 摇头点头: 4 个工具")
    print("  * head_shake_tool")
    print("  * head_nod_tool")
    print("  * continuous_head_shake_tool")
    print("  * continuous_head_nod_tool")
    print("- 位置控制: 2 个工具")
    print("  * move_camera_to_position")
    print("  * get_current_position")
    print("=" * 50)
    print(f"总计: 24 个工具")
    print("=" * 50)
    print("\nPTZ控制指令支持 (通过 ptz_control 或 natural_language_camera_control):")
    print("  方向控制（8个）: 上、下、左、右、一直上、一直下、一直左、一直右")
    print("  变焦控制（4个）: 放大、缩小、一直放大、一直缩小")
    print("  巡航控制（2个）: 一键巡航、停止巡航")
    print("  摄像头切换（4个）: 控制切换1、控制切换2、控制切换3、控制切换4")
    print("  预设点控制（10个）: 预设点1-预设点10")
    print(f"  总计: 30 种控制指令")
    print("=" * 50)
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
