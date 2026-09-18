import xml.etree.ElementTree as ET
import subprocess
import re

ADB = r"d:\DOCUMENTOS\KUSTOM_THEME\tools\platform-tools\adb.exe"

subprocess.run([ADB, "shell", "uiautomator", "dump", "/sdcard/window_dump.xml"], capture_output=True)
subprocess.run([ADB, "pull", "/sdcard/window_dump.xml", "dump_current.xml"], capture_output=True)

tree = ET.parse("dump_current.xml")
root = tree.getroot()

def parse_bounds(bounds_str):
    m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds_str)
    if m:
        x1, y1, x2, y2 = map(int, m.groups())
        return (x1 + x2) // 2, (y1 + y2) // 2
    return None

print("=== CURRENT SCREEN NODES ===")
for e in root.iter():
    t = e.attrib.get("text", "")
    d = e.attrib.get("content-desc", "")
    b = e.attrib.get("bounds", "")
    r = e.attrib.get("resource-id", "")
    if t or d:
        c = parse_bounds(b)
        print(f"TEXT: '{t}' | DESC: '{d}' | BOUNDS: {b} | CENTER: {c}")
