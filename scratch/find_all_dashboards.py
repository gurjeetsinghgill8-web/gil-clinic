import os, glob

dashboards = glob.glob('**/dashboard.html', recursive=True)
for d in dashboards:
    size = os.path.getsize(d)
    with open(d, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    has_cam = "camera-file-input" in content or "Camera Snap" in content
    print(f"Path: {d} | Size: {size} bytes | Has Camera Buttons?: {has_cam}")
