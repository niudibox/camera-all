import os
import json
import csv
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()

class PresetManager:
    """预设点管理模块"""
    
    def __init__(self):
        storage_path = os.getenv('PRESET_STORAGE_PATH')
        if storage_path:
            if not os.path.isabs(storage_path):
                camera_all_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                clean_path = storage_path.lstrip('./')
                self.storage_path = os.path.join(camera_all_dir, clean_path)
            else:
                self.storage_path = storage_path
        else:
            camera_all_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.storage_path = os.path.join(camera_all_dir, 'presets.csv')
        
        self.coordinate_tolerance = float(os.getenv('COORDINATE_TOLERANCE', '0.01'))
        self._ensure_storage_exists()
    
    def _ensure_storage_exists(self):
        if not os.path.exists(self.storage_path):
            with open(self.storage_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['name', 'coordinates'])
    
    def _parse_coordinates(self, coord_str: str) -> Tuple[float, float, float]:
        try:
            parts = coord_str.split(':')
            if len(parts) != 3:
                raise ValueError("坐标格式不正确，应为x:y:zoom")
            return float(parts[0]), float(parts[1]), float(parts[2])
        except Exception as e:
            raise ValueError(f"坐标解析失败: {str(e)}")
    
    def add_preset(self, name: str, x: float, y: float, zoom: float) -> Dict[str, any]:
        try:
            coordinates = f"{x}:{y}:{zoom}"
            
            existing_presets = []
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader, None)
                    for row in reader:
                        if len(row) >= 2:
                            existing_presets.append({'name': row[0], 'coordinates': row[1]})
            
            for preset in existing_presets:
                try:
                    existing_x, existing_y, existing_zoom = self._parse_coordinates(preset['coordinates'])
                    if (abs(existing_x - x) < self.coordinate_tolerance and
                        abs(existing_y - y) < self.coordinate_tolerance and
                        abs(existing_zoom - zoom) < self.coordinate_tolerance):
                        return {"success": False, "message": f"预设点已存在: {preset['name']}"}
                except:
                    pass
            
            with open(self.storage_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([name, coordinates])
            
            return {"success": True, "message": f"预设点已添加: {name}"}
        except Exception as e:
            return {"success": False, "message": f"添加预设点失败: {str(e)}"}
    
    def get_preset_by_name(self, name: str) -> Dict[str, any]:
        try:
            if not os.path.exists(self.storage_path):
                return {"success": False, "message": "预设点文件不存在"}
            
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    if len(row) >= 2 and row[0] == name:
                        return {"success": True, "preset": {"name": row[0], "coordinates": row[1]}}
            
            return {"success": False, "message": f"未找到预设点: {name}"}
        except Exception as e:
            return {"success": False, "message": f"读取预设点失败: {str(e)}"}
    
    def get_all_presets(self) -> Dict[str, any]:
        try:
            if not os.path.exists(self.storage_path):
                return {"success": False, "presets": [], "message": "预设点文件不存在"}
            
            presets = []
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    if len(row) >= 2:
                        presets.append({"name": row[0], "coordinates": row[1]})
            
            return {"success": True, "presets": presets}
        except Exception as e:
            return {"success": False, "presets": [], "message": f"读取预设点失败: {str(e)}"}
