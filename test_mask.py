import json, logging, numpy as np, cv2, sys, traceback
logging.basicConfig(level=logging.WARNING)

try:
    config = json.load(open(r"D:\Desktop\NexaTrans-0.1\config\settings.json"))
    region = config["region"]
    print(f"Region: {region['width']}x{region['height']}", flush=True)

    from screen.screenshot import capture_region
    img = capture_region(region)
    print(f"Screenshot: {img.shape}", flush=True)

    from detection.dbnet_detector import DBNetDetector
    det = DBNetDetector(limit_side_len=960)
    result = det.detect(img)
    boxes_p = result["boxes"]
    scores = result["scores"]
    print(f"Physical boxes: {len(boxes_p)}, scores: {scores}", flush=True)

    if not boxes_p:
        print("No boxes detected - test skipped", flush=True)
        sys.exit(0)

    dpr = 1.25
    logical_boxes = []
    for box in boxes_p:
        logical_boxes.append([int(round(c/dpr)) for c in box])
    print(f"Logical boxes: {len(logical_boxes)}", flush=True)

    from text_processing.mask_generator import MaskGenerator
    from text_processing.mask_refiner import MaskRefiner
    mg = MaskGenerator()
    mr = MaskRefiner()
    mask = mg.generate((region["height"], region["width"]), logical_boxes)
    refined = mr.refine(mask)
    print(f"Mask: {refined.shape}, nonzero={np.count_nonzero(refined)}", flush=True)

    img_log = cv2.resize(img, (region["width"], region["height"]))
    from detection.detection_pipeline import DetectionPipeline
    colors = []
    for box in logical_boxes:
        c = DetectionPipeline._sample_background_color(img_log, box)
        colors.append(c)
    print(f"Colors: {len(colors)}", flush=True)
    for i, c in enumerate(colors):
        print(f"  Box {i+1}: BGR=({c[0]},{c[1]},{c[2]})", flush=True)

    from overlay.text_overlay import TextOverlay
    ov = TextOverlay()
    ov._boxes = logical_boxes
    ov.update_mask(refined, colors)
    print(f"Has pixmap: {ov._mask_pixmap is not None}", flush=True)
    print("TEST PASSED", flush=True)
except Exception as e:
    traceback.print_exc()
    print(f"TEST FAILED: {e}", flush=True)
