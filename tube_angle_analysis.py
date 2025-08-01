import cv2, numpy as np, csv, pytesseract, math, os, json, datetime, pandas as pd

pytesseract.pytesseract.tesseract_cmd = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

def get_point(window, frame, prompt):
    print(prompt)
    pts = []
    def click(e,x,y,f,p):
        if e == cv2.EVENT_LBUTTONDOWN:
            pts.append((x, y))
            cv2.circle(frame,(x,y),5,(0,255,0),-1)
            cv2.imshow(window,frame)
    cv2.imshow(window,frame)
    cv2.setMouseCallback(window,click)
    while len(pts)<1: cv2.waitKey(1)
    cv2.destroyWindow(window)
    return pts[0]

def get_angle(center, pt):
    dx, dy = pt[0]-center[0], center[1]-pt[1]
    return (math.degrees(math.atan2(dy, dx)) + 360) % 360

def map_to_arc(angle, a0, a90):
    if a90 < a0: a90 += 360
    if angle < a0: angle += 360
    return 180 * (angle - a0) / (a90 - a0)  # now maps to 0–180°

def detect_pressure(frame, roi, save_path=None, crossing_label=None):
    x, y, w, h = roi
    cropped = frame[int(y):int(y+h), int(x):int(x+w)]
    if save_path and crossing_label is not None:
        debug_file = os.path.join(save_path, f"pressure_at_{crossing_label}deg.png")
        cv2.imwrite(debug_file, cropped)
    gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                   cv2.THRESH_BINARY_INV, 31, 15)
    config = '--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789'
    txt = pytesseract.image_to_string(thresh, config=config)
    try:
        return int(txt.strip())
    except:
        return None

def configure_video(video_path, batch_mode=False):
    cap=cv2.VideoCapture(video_path); ret,frame=cap.read(); cap.release()
    if not ret: raise ValueError(f"Could not read {video_path}")
    print(f"\nConfiguring: {os.path.basename(video_path)}")
    if batch_mode:
        run_name = ""  # Skip run name in batch mode
    else:
        run_name = input("Enter run name for this video: ").strip()
    origin = get_point("Origin", frame.copy(),"Click protractor origin/pivot.")
    tube_tip_point = get_point("Tube Tip", frame.copy(),"Click tube tip (center of tube).")
    pt0 = get_point("0°", frame.copy(),"Click 0° reference.")
    pt90 = get_point("90°", frame.copy(),"Click 90° reference.")
    print("Select a ROI around the tube tip and press SPACE or ENTER button!")
    tube_tip_box = cv2.selectROI(f"Tube Tip Tracking Box - {os.path.basename(video_path)}", frame, False); cv2.destroyWindow(f"Tube Tip Tracking Box - {os.path.basename(video_path)}")
    print("Select a ROI around the protractor and press SPACE or ENTER button!")
    protractor_roi = cv2.selectROI(f"Protractor ROI - {os.path.basename(video_path)}", frame, False); cv2.destroyWindow(f"Protractor ROI - {os.path.basename(video_path)}")
    print("Select a ROI around the pressure display and press SPACE or ENTER button!")
    pressure_roi = cv2.selectROI(f"Pressure Display - {os.path.basename(video_path)}", frame, False); cv2.destroyWindow(f"Pressure Display - {os.path.basename(video_path)}")
    return {
        "video": video_path,
        "run_name": run_name,
        "origin": origin,
        "pt0": pt0,
        "pt90": pt90,
        "tube_tip_box": tube_tip_box,
        "protractor_roi": protractor_roi,
        "pressure_roi": pressure_roi
    }

def process_video(config, spacing):
    VIDEO_PATH = config["video"]
    video_name = os.path.splitext(os.path.basename(VIDEO_PATH))[0]
    if config["run_name"]:
        folder_name = f"{video_name}_{config['run_name']}"
    else:
        folder_name = video_name
    OUTPUT_DIR = os.path.join(os.getcwd(), "AnnotatedResults", folder_name)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    OUTPUT_VIDEO = os.path.join(OUTPUT_DIR, f"{video_name}_annotated.mp4")
    OUTPUT_CSV = os.path.join(OUTPUT_DIR, "tube_crossings.csv")

    SPACING = spacing
    RETRACE_THRESHOLD = 10.0
    angle0, angle90 = get_angle(config["origin"], config["pt0"]), get_angle(config["origin"], config["pt90"])
    target_angles = np.arange(0,181,SPACING).tolist()
    tolerance = SPACING / 2

    cap=cv2.VideoCapture(VIDEO_PATH)
    try: tracker = cv2.legacy.TrackerCSRT_create()
    except: tracker = cv2.TrackerCSRT_create()
    ret,frame=cap.read()
    tracker.init(frame, config["tube_tip_box"])
    fps=cap.get(cv2.CAP_PROP_FPS)
    w,h=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc=cv2.VideoWriter_fourcc(*'mp4v'); out=cv2.VideoWriter(OUTPUT_VIDEO,fourcc,fps,(w,h))

    csv_file = open(OUTPUT_CSV,'w',newline='')
    csv_file.write(f"# Video: {os.path.basename(VIDEO_PATH)}\n")
    csv_file.write(f"# Exported: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    csv_file.write(f"# Angle Spacing: {SPACING}°\n")
    writer = csv.writer(csv_file)
    writer.writerow(["Frame","Time(MM:SS)","CrossedAngle(deg)","Pressure(PSI)"])
    crossed=set(); last=-999; frame_idx=0; summary=[]
    start_angle=None; end_angle=None

    while True:
        ret,frame=cap.read()
        if not ret: break
        success, bbox = tracker.update(frame)
        if not success: break
        tip_center = (int(bbox[0]+bbox[2]/2), int(bbox[1]+bbox[3]/2))
        current = map_to_arc(get_angle(config["origin"], tip_center), angle0, angle90)
        current = max(0,min(180,current))
        if start_angle is None: start_angle = current
        end_angle = current
        for mark in target_angles:
            if (mark not in crossed or (mark < last - RETRACE_THRESHOLD)) and (abs(current - mark) <= tolerance):
                crossed.add(mark); last=mark
                pressure = detect_pressure(frame, config["pressure_roi"], save_path=OUTPUT_DIR, crossing_label=mark)
                secs=int(frame_idx/fps); t=f"{secs//60:02}:{secs%60:02}"
                writer.writerow([frame_idx,t,mark,pressure if pressure is not None else ""])
                summary.append((mark,t,pressure))
        # Draw markers
        x,y,rw,rh=config["protractor_roi"]
        for mark in target_angles:
            theta=(angle0+(angle90-angle0)*(mark/90))%360
            rad=math.radians(theta); radius=rw/1.5
            px=int(config["origin"][0]+radius*math.cos(rad)); py=int(config["origin"][1]-radius*math.sin(rad))
            color=(0,255,0) if mark in crossed else (0,0,255)
            cv2.circle(frame,(px,py),3,color,-1)
            cv2.putText(frame,str(int(mark)),(px+5,py-5),cv2.FONT_HERSHEY_SIMPLEX,0.4,color,1)
        # Tracker box
        p1 = (int(bbox[0]), int(bbox[1]))
        p2 = (int(bbox[0]+bbox[2]), int(bbox[1]+bbox[3]))
        cv2.rectangle(frame, p1, p2, (255,0,0), 2)
        out.write(frame); frame_idx+=1

    cap.release(); out.release(); csv_file.close(); cv2.destroyAllWindows()

    # Run report
    report_data = {
        "video": os.path.basename(VIDEO_PATH),
        "exported": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "angle_spacing": SPACING,
        "start_angle": start_angle,
        "end_angle": end_angle,
        "crossings": [{"angle": a, "time": t, "pressure": p} for a,t,p in summary]
    }
    report_path = os.path.join(OUTPUT_DIR, "run_report.json")
    with open(report_path, 'w') as jf: json.dump(report_data, jf, indent=4)

    # Montage
    pressure_images = []
    for a, _, _ in summary:
        img_path = os.path.join(OUTPUT_DIR, f"pressure_at_{a}deg.png")
        if os.path.exists(img_path):
            img = cv2.imread(img_path)
            if img is not None:
                cv2.putText(img, f"{a}°", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)
                pressure_images.append(img)
    if pressure_images:
        max_h = max(img.shape[0] for img in pressure_images)
        resized = [cv2.resize(img, (int(img.shape[1] * max_h / img.shape[0]), max_h)) for img in pressure_images]
        montage = cv2.hconcat(resized)
        montage_path = os.path.join(OUTPUT_DIR, "pressure_montage.png")
        cv2.imwrite(montage_path, montage)

    # Update master reports
    master_report_path = os.path.join(os.getcwd(), "AnnotatedResults", "master_report.json")
    all_reports = []
    if os.path.exists(master_report_path):
        with open(master_report_path, 'r') as mf:
            try: all_reports = json.load(mf)
            except: all_reports = []
    all_reports = [r for r in all_reports if r.get("video") != os.path.basename(VIDEO_PATH)]
    all_reports.append(report_data)
    with open(master_report_path, 'w') as mf: json.dump(all_reports, mf, indent=4)

    master_csv_path = os.path.join(os.getcwd(), "AnnotatedResults", "master_report.csv")
    flat_data = []
    for r in all_reports:
        for c in r["crossings"]:
            flat_data.append({
                "Video": r["video"],
                "Exported": r["exported"],
                "AngleSpacing": r.get("angle_spacing", ""),
                "Time(MM:SS)": c["time"],
                "CrossedAngle(deg)": c["angle"],
                "Pressure(PSI)": c["pressure"],
                "StartAngle": r["start_angle"],
                "EndAngle": r["end_angle"]
            })
    df = pd.DataFrame(flat_data)
    df['Exported'] = pd.to_datetime(df['Exported'], errors='coerce')
    df = df.sort_values(by=['Exported','Video'], ascending=[False, True])
    df.to_csv(master_csv_path, index=False)

    print(f"Processed {os.path.basename(VIDEO_PATH)} ({len(summary)} crossings).")
    return len(summary)

# === MAIN ===
mode = input("Select mode: 1 - Single video, 2 - Batch folder: ").strip()
spacing = int(input("Enter angle spacing (e.g., 10): ").strip())
video_configs = []
if mode == "1":
    LAST_PATH_FILE = "last_path.txt"
    if os.path.exists(LAST_PATH_FILE):
        with open(LAST_PATH_FILE, 'r') as f: last_dir = f.read().strip()
    else: last_dir = os.getcwd()
    video_name = input(f"Enter video filename (in {last_dir}): ").strip()
    VIDEO_PATH = os.path.join(last_dir, video_name) if not os.path.isabs(video_name) else video_name
    with open(LAST_PATH_FILE, 'w') as f: f.write(os.path.dirname(VIDEO_PATH))
    video_configs.append(configure_video(VIDEO_PATH, batch_mode=False))
else:
    folder = input("Enter folder path with videos: ").strip()
    videos = [os.path.join(folder,f) for f in os.listdir(folder) if f.lower().endswith(('.mp4','.mov','.avi'))]
    videos.sort()
    for v in videos:
        video_configs.append(configure_video(v, batch_mode=True))

# Process all
total_crossings = 0
for cfg in video_configs:
    total_crossings += process_video(cfg, spacing)

print("\n=== Batch Processing Complete ===")
print(f"Total videos processed: {len(video_configs)}")
print(f"Total crossings recorded: {total_crossings}")
print(f"Master report updated at: {os.path.abspath(os.path.join(os.getcwd(), 'AnnotatedResults', 'master_report.csv'))}")
