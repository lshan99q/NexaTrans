import sys
from config.config_manager import ConfigManager
c = ConfigManager()
print("Config OK", flush=True)
from detection.detection_pipeline import DetectionPipeline
p = DetectionPipeline(c, target_fps=5)
print("Detector loaded:", p.detector.is_loaded, flush=True)
print("Pipeline init OK", flush=True)
