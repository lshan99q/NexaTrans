"""
NexaTrans - Config Manager
配置文件读写管理模块
"""

import json
import os
import logging

logger = logging.getLogger("NexaTrans.Config")

# 默认配置
DEFAULT_CONFIG = {
    "region": {
        "x": 0,
        "y": 0,
        "width": 500,
        "height": 80
    },
    "overlay": {
        "opacity": 0.5,
        "border": True
    }
}


class ConfigManager:
    """配置管理器，负责 settings.json 的读写"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            # 默认路径：项目根目录下的 config/settings.json
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.config_path = os.path.join(base_dir, "config", "settings.json")
        else:
            self.config_path = config_path

        self.config_dir = os.path.dirname(self.config_path)
        self._ensure_config_dir()
        self._ensure_config_file()

    def _ensure_config_dir(self):
        """确保配置目录存在"""
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir, exist_ok=True)
            logger.info(f"创建配置目录: {self.config_dir}")

    def _ensure_config_file(self):
        """确保配置文件存在，不存在则创建默认配置"""
        if not os.path.exists(self.config_path):
            self._write_config(DEFAULT_CONFIG)
            logger.info(f"创建默认配置文件: {self.config_path}")

    def _read_config(self) -> dict:
        """读取完整配置"""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"读取配置文件失败: {e}，使用默认配置")
            return dict(DEFAULT_CONFIG)

    def _write_config(self, config: dict):
        """写入完整配置"""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            logger.info("配置已保存")
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")

    def save_region(self, region: dict):
        """
        保存区域坐标

        参数:
            region: {
                "x": int,
                "y": int,
                "width": int,
                "height": int
            }
        """
        config = self._read_config()
        config["region"] = {
            "x": int(region.get("x", 0)),
            "y": int(region.get("y", 0)),
            "width": int(region.get("width", 0)),
            "height": int(region.get("height", 0))
        }
        self._write_config(config)

    def load_region(self) -> dict:
        """
        读取区域坐标

        返回:
            {
                "x": int,
                "y": int,
                "width": int,
                "height": int
            }
        """
        config = self._read_config()
        return dict(config.get("region", DEFAULT_CONFIG["region"]))

    def get_overlay_config(self) -> dict:
        """获取覆盖层配置"""
        config = self._read_config()
        return dict(config.get("overlay", DEFAULT_CONFIG["overlay"]))