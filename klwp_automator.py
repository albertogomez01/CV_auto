import xml.etree.ElementTree as ET
import subprocess
import time
import sys
import re

ADB = r"d:\DOCUMENTOS\KUSTOM_THEME\tools\platform-tools\adb.exe"

def run_adb(args):
    cmd = [ADB] + args
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.stdout.strip()

def tap(x, y):
    print(f"[TAP] Tapping ({x}, {y})")
    run_adb(["shell", "input", "tap", str(x), str(y)])
    time.sleep(1.5)

def parse_bounds(bounds_str):
    # "[208,1477][495,1536]"
    m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds_str)
    if m:
        x1, y1, x2, y2 = map(int, m.groups())
        return (x1 + x2) // 2, (y1 + y2) // 2
    return None

def get_elements():
    run_adb(["shell", "uiautomator", "dump", "/sdcard/window_dump.xml"])
    run_adb(["pull", "/sdcard/window_dump.xml", "dump.xml"])
    try:
        tree = ET.parse("dump.xml")
        root = tree.getroot()
    except Exception as e:
        print("XML parse error:", e)
        return []
    
    elems = []
    for e in tree.iter():
        txt = e.attrib.get("text", "")
        desc = e.attrib.get("content-desc", "")
        bounds = e.attrib.get("bounds", "")
        res = e.attrib.get("resource-id", "")
        if txt or desc:
            elems.append({
                "text": txt,
                "desc": desc,
                "bounds": bounds,
                "res": res,
                "center": parse_bounds(bounds)
            })
    return elems

def main():
    print("=== KLWP AUTOMATION STEP ===")
    elems = get_elements()
    print("Found UI elements:")
    target_preset = None
    folder_icon = None
    exportados_tab = None
    guardados_tab = None
    
    for el in elems:
        t = el["text"]
        d = el["desc"]
        b = el["bounds"]
        print(f"  TEXT: '{t}' | DESC: '{d}' | BOUNDS: {b}")
        
        if "BW_Editorial" in t or "BW_Editorial" in d or "A55" in t or "A55" in d:
            target_preset = el
        if "EXPORTADOS" in t.upper() or "EXPORTADOS" in d.upper():
            exportados_tab = el
        if "GUARDADOS" in t.upper() or "GUARDADOS" in d.upper():
            guardados_tab = el
        if "CARPETA" in t.upper() or "FOLDER" in d.upper() or "ABRIR" in t.upper():
            folder_icon = el

    if target_preset:
        print(f"FOUND PRESET: {target_preset}")
        cx, cy = target_preset["center"]
        tap(cx, cy)
    elif exportados_tab:
        print(f"Tapping Exportados tab: {exportados_tab}")
        cx, cy = exportados_tab["center"]
        tap(cx, cy)
    elif guardados_tab:
        print(f"Tapping Guardados tab: {guardados_tab}")
        cx, cy = guardados_tab["center"]
        tap(cx, cy)
    else:
        print("No direct preset found yet. Checking folder / file picker...")
        # Check top bar folder icon or import button
        for el in elems:
            if "Import" in el["text"] or "Import" in el["desc"] or "Folder" in el["desc"]:
                print(f"Tapping icon: {el}")
                cx, cy = el["center"]
                tap(cx, cy)
                break

if __name__ == "__main__":
    main()
