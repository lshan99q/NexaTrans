from config.config_manager import ConfigManager
c = ConfigManager()
print("Config OK")
from detection.detection_pipeline import DetectionPipeline
p = DetectionPipeline(c, target_fps=5)
print("Detector loaded:", p.detector.is_loaded)
print("Pipeline init OK")
