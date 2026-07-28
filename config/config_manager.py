"""
NexaTrans - Config Manager
Configuration file read/write management module.
"""

import json
import os
import logging

logger = logging.getLogger("NexaTrans.Config")

DEFAULT_CONFIG = {
    "region": {
        "x": 0,
        "y": 0,
        "width": 500,
        "height": 80,
    },
    "overlay": {
        "opacity": 0.5,
        "border": True,
    },
    "text_processing": {
        "dilate_size": 5,
        "blur_size": 3,
        "merge_distance": 20,
        "height_ratio": 0.6,
        "crop_padding": 2,
        "min_confidence": 0.5,
        "min_text_aspect": 1.8,
        "max_icon_aspect": 1.4,
        "min_area_ratio": 0.005,
    },
    "ocr": {
        "enabled": False,
        "engine": "PP-OCRv5",
        "confidence": 0.7,
        "cache": True,
        "lang": "ch",
    },
}


class ConfigManager:
    """Configuration manager for settings.json read/write."""

    def __init__(self, config_path: str = None):
        if config_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.config_path = os.path.join(base_dir, "config", "settings.json")
        else:
            self.config_path = config_path

        self.config_dir = os.path.dirname(self.config_path)
        self._ensure_config_dir()
        self._ensure_config_file()

    def _ensure_config_dir(self):
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir, exist_ok=True)
            logger.info(f"Created config directory: {self.config_dir}")

    def _ensure_config_file(self):
        if not os.path.exists(self.config_path):
            self._write_config(DEFAULT_CONFIG)
            logger.info(f"Created default config file: {self.config_path}")

    def _read_config(self) -> dict:
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            # Merge defaults for any missing top-level keys
            for key in DEFAULT_CONFIG:
                if key not in config:
                    config[key] = dict(DEFAULT_CONFIG[key])
            return config
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Failed to read config: {e}, using defaults")
            return dict(DEFAULT_CONFIG)

    def _write_config(self, config: dict):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            logger.info("Config saved")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def save_region(self, region: dict):
        config = self._read_config()
        config["region"] = {
            "x": int(region.get("x", 0)),
            "y": int(region.get("y", 0)),
            "width": int(region.get("width", 0)),
            "height": int(region.get("height", 0)),
        }
        self._write_config(config)

    def load_region(self) -> dict:
        config = self._read_config()
        return dict(config.get("region", DEFAULT_CONFIG["region"]))

    def get_overlay_config(self) -> dict:
        config = self._read_config()
        return dict(config.get("overlay", DEFAULT_CONFIG["overlay"]))

    def get_text_processing_config(self) -> dict:
        config = self._read_config()
        return dict(config.get("text_processing", DEFAULT_CONFIG["text_processing"]))

    def save_text_processing(self, tp: dict):
        config = self._read_config()
        config["text_processing"] = dict(tp)
        self._write_config(config)

    def get_ocr_config(self) -> dict:
        config = self._read_config()
        return dict(config.get("ocr", DEFAULT_CONFIG["ocr"]))

    def save_ocr_config(self, ocr: dict):
        config = self._read_config()
        config["ocr"] = dict(ocr)
        self._write_config(config)
