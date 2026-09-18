import xml.etree.ElementTree as ET
import subprocess
import time
import re

ADB = r"d:\DOCUMENTOS\KUSTOM_THEME\tools\platform-tools\adb.exe"

def run_adb(args):
    res = subprocess.run([ADB] + args, capture_output=True, text=True)
    return res.stdout.strip()

def tap(x, y, desc=""):
    print(f"[TAP] Tapping ({x}, {y}) - {desc}")
    run_adb(["shell", "input", "tap", str(x), str(y)])
    time.sleep(2.5)

def parse_bounds(bounds_str):
    m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds_str)
    if m:
        x1, y1, x2, y2 = map(int, m.groups())
        return (x1 + x2) // 2, (y1 + y2) // 2
    return None

def dump_and_get():
    run_adb(["shell", "uiautomator", "dump", "/sdcard/window_dump.xml"])
    run_adb(["pull", "/sdcard/window_dump.xml", "dump_temp.xml"])
    try:
        tree = ET.parse("dump_temp.xml")
        root = tree.getroot()
        elems = []
        for e in root.iter():
            t = e.attrib.get("text", "")
            d = e.attrib.get("content-desc", "")
            b = e.attrib.get("bounds", "")
            r = e.attrib.get("resource-id", "")
            if t or d:
                elems.append({
                    "text": t, "desc": d, "bounds": b, "res": r, "center": parse_bounds(b)
                })
        return elems
    except Exception as e:
        print("Error parsing dump:", e)
        return []

def main():
    print("=== PASO 1: Seleccionando archivo BW_Editorial_A55.klwp ===")
    tap(351, 1506, "BW_Editorial_A55.klwp")
    
    elems = dump_and_get()
    print("UI after file selection:")
    for el in elems:
        print(f"  TEXT: '{el['text']}' | DESC: '{el['desc']}' | BOUNDS: {el['bounds']}")
    
    print("\n=== PASO 2: Guardando preset en KLWP (Boton Guardar) ===")
    save_btn = None
    for el in elems:
        if "Guardar" in el["desc"] or "Save" in el["desc"]:
            save_btn = el
            break
            
    if save_btn and save_btn["center"]:
        tap(save_btn["center"][0], save_btn["center"][1], "Icono Guardar")
    else:
        # Fallback coordinates for save icon in KLWP editor top bar: (742, 162)
        tap(742, 162, "Icono Guardar (Coordenadas)")
        
    elems2 = dump_and_get()
    print("UI after Save:")
    for el in elems2:
        print(f"  TEXT: '{el['text']}' | DESC: '{el['desc']}' | BOUNDS: {el['bounds']}")
        
    # Check if there is a popup or button like "Solucionar", "Establecer", "Aplicar", "CORREGIR"
    for el in elems2:
        txt = el["text"].upper()
        desc = el["desc"].upper()
        if any(w in txt or w in desc for w in ["SOLUCIONAR", "CORREGIR", "ESTABLECER", "APLICAR", "FIX", "ACEPTAR", "PERMITIR"]):
            print(f"FOUND ACTION BUTTON: {el}")
            if el["center"]:
                tap(el["center"][0], el["center"][1], f"Boton {el['text'] or el['desc']}")

if __name__ == "__main__":
    main()
