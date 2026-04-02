# Camera All - 统一摄像头 MCP 服务器

整合了 `camera-tools` 和 `cameras` 项目的所有功能，提供统一的摄像头控制接口。

## 项目结构

```
camera-all/
├── core/                      # 核心模块
│   ├── camera_controller.py   # 摄像头控制器
│   └── preset_manager.py      # 预设点管理器
├── tools/                     # 工具模块（按功能分类）
│   ├── motion/                # 云台控制工具
│   │   ├── motion_tools.py           # 云台控制（13个工具）
│   │   ├── head_motion_tools.py      # 摇头点头（4个工具）
│   │   └── initial_position_tools.py # 位置初始化（2个工具）
│   ├── preset/                # 预设点管理工具
│   │   └── preset_tools.py            # 预设点管理（5个工具）
│   ├── vision/                # 视觉识别工具
│   │   └── vision_tools.py            # 视觉识别（2个工具）
│   └── initial_position.json  # 初始位置数据
├── main.py                    # 主程序入口
├── requirements.txt           # Python 依赖
├── .env.example               # 环境变量示例
├── .gitignore                 # Git 忽略配置
└── README.md                  # 项目文档
```

## 功能特性

### 预设点管理（5个工具）
- `get_position_and_name` - 获取当前画面坐标与命名
- `add_manual_preset` - 写入手动预设点
- `get_manual_preset` - 读取手动预设点
- `import_system_presets` - 系统预设点导入与命名
- `scan_full_view` - 全视野扫描

### 云台控制（13个工具）
- `EyeCam` - 摄像头视觉识别功能
- `ptz_control` - PTZ 命令控制
- `move_camera` - 控制摄像头向指定方向移动
- `clear_obstruction_tool` - 控制摄像头向上移动以开启视线遮挡
- `start_cruise_tool` - 启动自动巡视
- `stop_cruise_tool` - 停止自动巡视
- `switch_camera_tool` - 切换摄像头
- `natural_language_camera_control` - 通过自然语言控制摄像头移动
- `reset_camera_position` - 重置摄像头位置到初始状态
- `move_camera_to_position` - 将摄像头移动到指定坐标
- `get_current_position` - 获取摄像头当前位置
- `get_system_presets_tool` - 获取系统预设点
- `move_to_preset_tool` - 移动到预设点

### 摇头点头（4个工具）
- `head_shake_tool` - 摄像头左右摇摆
- `head_nod_tool` - 摄像头上下的点头动作
- `continuous_head_shake_tool` - 持续左右摇摆
- `continuous_head_nod_tool` - 持续上下点头

### 位置初始化（2个工具）
- `save_initial_position` - 保存初始位置
- `get_saved_initial_position` - 获取已保存的初始位置

## 安装步骤

### 1. 安装依赖

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并修改配置：

```bash
cp .env.example .env
```

主要配置项：
- `ONVIF_CAMERA_IP` - 摄像头 IP 地址
- `ONVIF_CAMERA_PORT` - 摄像头端口
- `ONVIF_CAMERA_USERNAME` - 摄像头用户名
- `ONVIF_CAMERA_PASSWORD` - 摄像头密码
- `ONVIF_CAMERA_PTZ_ENABLED` - 是否启用 PTZ 控制（true/false）
- `RTSP_CAMERA_IP` - RTSP 流 IP 地址
- `RTSP_CAMERA_PORT` - RTSP 流端口
- `AI_API_URL` - AI 视觉识别 API 地址
- `AI_API_TOKEN` - AI API 认证令牌

## 使用方法

### 启动服务器

```bash
python main.py
```

### 在 MCP 客户端中使用

在 MCP 客户端配置中添加：

```json
{
  "mcpServers": {
    "camera-all": {
      "command": "python",
      "args": ["/path/to/camera-all/main.py"]
    }
  }
}
```

## 工具使用示例

### 预设点管理

```python
# 获取当前位置并生成名称
get_position_and_name(question="请描述这个位置")

# 添加手动预设点
add_manual_preset(name="客厅", coordinates="0.5:0.3:0.2")

# 读取预设点
get_manual_preset(name="客厅")

# 导入系统预设点
import_system_presets()
```

### 云台控制

```python
# 移动摄像头
move_camera(direction="left", speed=0.5)

# 自动巡视
start_cruise_tool()

# 自然语言控制
natural_language_camera_control(command="一直向左")

# 重置位置
reset_camera_position()

# 切换摄像头（1-4）
switch_camera_tool(camera_index=1)
```

### 摇头点头

```python
# 左右摇摆
head_shake_tool(speed=0.8, duration=0.3)

# 上下点头
head_nod_tool(speed=0.8, duration=0.3)
```

### 视觉识别

```python
# 捕获并识别图像
capture_image(question="请描述这张图片的内容")

# 获取最新帧
get_latest_frame()
```

## 配置说明

### 摄像头移动速度

- `DEFAULT_CAMERA_SPEED` - 默认移动速度（0.1-1.0）
- `MAX_CAMERA_SPEED` - 最大移动速度
- `MIN_CAMERA_SPEED` - 最小移动速度

### 移动指令时间

- `PATROL_DURATION` - 巡视持续时间（秒）
- `CONTINUOUS_MOVE_DURATION` - 持续移动时间（秒）
- `SHORT_MOVE_DURATION` - 短距离移动时间（秒）
- `CLEAR_OBSTRUCTION_DURATION` - 清除遮挡移动时间（秒）

### AI 视觉交互

- `AI_API_URL` - AI 识别 API 地址
- `AI_API_TOKEN` - API 认证令牌
- `AI_TIMEOUT` - 请求超时时间（秒）

### 预设点存储

- `PRESET_STORAGE_PATH` - 预设点存储文件路径
- `COORDINATE_TOLERANCE` - 坐标误差容忍度

### 多摄像头支持

支持配置多个摄像头，通过 `switch_camera_tool` 切换：
- `ONVIF_CAMERA_IP` / `RTSP_CAMERA_IP` - 摄像头1
- `ONVIF_CAMERA_IP_2` / `RTSP_CAMERA_IP_2` - 摄像头2
- `ONVIF_CAMERA_IP_3` / `RTSP_CAMERA_IP_3` - 摄像头3
- `ONVIF_CAMERA_IP_4` / `RTSP_CAMERA_IP_4` - 摄像头4

## 依赖项

- `python-dotenv` - 环境变量管理
- `mcp` - MCP 服务器框架
- `opencv-python` - 图像处理
- `onvif-zeep` - ONVIF 协议支持
- `getmac` - MAC 地址获取
- `requests` - HTTP 请求
- `Pillow` - 图像处理
- `numpy` - 数值计算

## 注意事项

1. 确保摄像头支持 ONVIF 协议
2. 确保 RTSP 流地址正确
3. 确保 AI API 配置正确（如需使用视觉识别功能）
4. 首次使用建议先测试摄像头连接
5. `.env` 文件包含敏感信息，请勿提交到 Git

## 故障排除

### 摄像头连接失败
- 检查 IP 地址、端口、用户名、密码是否正确
- 确保摄像头支持 ONVIF 协议
- 检查网络连接

### 视觉识别失败
- 检查 AI API 地址和令牌是否正确
- 检查网络连接
- 检查 API 服务是否可用

### PTZ 控制无效
- 确认 `ONVIF_CAMERA_PTZ_ENABLED` 设置为 `true`
- 确认摄像头支持 PTZ 功能
- 检查媒体配置文件令牌是否正确

## 版本历史

### v1.0.0
- 整合 camera-tools 和 cameras 项目
- 合并核心模块，减少冗余
- 按功能分类工具模块
- 提供统一的 MCP 服务器接口
- 总共 24 个工具

## 许可证

本项目基于原 camera-tools 和 cameras 项目整合而来。
