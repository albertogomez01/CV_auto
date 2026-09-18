import xml.etree.ElementTree as ET
import subprocess
import time
import re

ADB = r"d:\DOCUMENTOS\KUSTOM_THEME\tools\platform-tools\adb.exe"

def run_adb(args):
    res = subprocess.run([ADB] + args, capture_output=True, text=True)
    return res.stdout.strip()

def tap(x, y, label=""):
    print(f"[TAP] Tapping ({x}, {y}) - {label}")
    run_adb(["shell", "input", "tap", str(x), str(y)])
    time.sleep(2.0)

def parse_bounds(bounds_str):
    m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds_str)
    if m:
        x1, y1, x2, y2 = map(int, m.groups())
        return (x1 + x2) // 2, (y1 + y2) // 2
    return None

def get_screen_nodes():
    run_adb(["shell", "uiautomator", "dump", "/sdcard/window_dump.xml"])
    run_adb(["pull", "/sdcard/window_dump.xml", "dump_live.xml"])
    try:
        tree = ET.parse("dump_live.xml")
        root = tree.getroot()
        elems = []
        for e in root.iter():
            t = e.attrib.get("text", "")
            d = e.attrib.get("content-desc", "")
            b = e.attrib.get("bounds", "")
            if t or d:
                elems.append({"text": t, "desc": d, "bounds": b, "center": parse_bounds(b)})
        return elems
    except Exception as e:
        print("XML error:", e)
        return []

def main():
    print("=== INICIANDO CONFIGURACION COMPLETA DE KLWP ===")
    
    # 1. Abrir KLWP
    print("1. Abriendo KLWP...")
    run_adb(["shell", "monkey", "-p", "org.kustom.wallpaper", "1"])
    time.sleep(3.0)
    
    elems = get_screen_nodes()
    print("Menu Principal KLWP:")
    for e in elems:
        print(f"  TEXT: '{e['text']}' | DESC: '{e['desc']}' | BOUNDS: {e['bounds']}")
        
    # 2. Si estamos en editor, pulsar guardar. Si estamos en menu, cargar preset.
    save_found = False
    for e in elems:
        if "Guardar" in e["desc"]:
            save_found = True
            tap(e["center"][0], e["center"][1], "Boton Guardar en Editor")
            break
            
    if not save_found:
        # Tocar 'Crear' o 'Cargar Predefinido'
        for e in elems:
            if "Crear" in e["text"]:
                tap(e["center"][0], e["center"][1], "Boton Crear")
                break
        time.sleep(2.0)
        # Pulsar Guardar (742, 162)
        tap(742, 162, "Icono Guardar")

    time.sleep(3.0)
    # 3. Revisar si aparecio la pantalla del sistema 'Establecer como fondo'
    elems2 = get_screen_nodes()
    print("\nPantalla tras guardar:")
    for e in elems2:
        print(f"  TEXT: '{e['text']}' | DESC: '{e['desc']}' | BOUNDS: {e['bounds']}")
        
    # Buscar botones del sistema como "Establecer como fondo de pantalla", "Aplicar", "Pantalla de inicio"
    target_btn = None
    for e in elems2:
        txt = (e["text"] + " " + e["desc"]).upper()
        if any(w in txt for w in ["ESTABLECER", "APLICAR", "FONDO DE PANTALLA", "SOLUCIONAR", "FIX", "DEFINIR"]):
            target_btn = e
            break
            
    if target_btn and target_btn["center"]:
        tap(target_btn["center"][0], target_btn["center"][1], f"Pulsando {target_btn['text'] or target_btn['desc']}")
        time.sleep(2.0)
        # Si pide Elegir "Pantalla de inicio y de bloqueo"
        elems3 = get_screen_nodes()
        for e in elems3:
            txt = (e["text"] + " " + e["desc"]).upper()
            if "INICIO" in txt or "BLOQUEO" in txt:
                if e["center"]:
                    tap(e["center"][0], e["center"][1], "Pantalla de inicio y de bloqueo")
                    break

    # Volver al Home
    run_adb(["shell", "input", "keyevent", "3"])
    print("=== PROCESO FINALIZADO ===")

if __name__ == "__main__":
    main()
