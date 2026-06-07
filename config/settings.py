"""
应用程序配置管理模块
"""
import json
import os
import sys
from typing import Dict, Any

from utils.app_paths import user_data_file


class Settings:
    """应用程序设置管理类"""
    
    def __init__(self, config_file: str | None = None):
        if config_file is None:
            if getattr(sys, "frozen", False):
                self.config_file = user_data_file("config.json")
            else:
                self.config_file = "config.json"
        else:
            self.config_file = config_file
        self.settings = self._load_settings()
    
    def _load_settings(self) -> Dict[str, Any]:
        """加载设置"""
        default_settings = {
            "window": {
                "width": 1100,
                "height": 700,
                "theme": "light"
            },
            "analysis": {
                "max_sequence_length": 1000000,
                "default_output_format": "fasta"
            },
            "directories": {
                "last_input_dir": "",
                "last_output_dir": ""
            },
            "recent_files": []
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    # 合并默认设置
                    for key, value in default_settings.items():
                        if key not in settings:
                            settings[key] = value
                    return settings
            except Exception:
                return default_settings
        
        return default_settings
    
    def save_settings(self):
        """保存设置"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存设置失败: {e}")
    
    def get(self, key_path: str, default=None):
        """获取设置值"""
        keys = key_path.split('.')
        value = self.settings
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value
    
    def set(self, key_path: str, value):
        """设置值"""
        keys = key_path.split('.')
        current = self.settings
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value
        self.save_settings()
