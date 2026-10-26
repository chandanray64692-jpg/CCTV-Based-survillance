
from pathlib import Path
import py_compile

path = Path("core/views.py")
if not path.exists():
    print("Error: core/views.py not found!")
    exit(1)

text = path.read_text(encoding="utf-8")

# 1. ThreadPoolExecutor import fix
text = text.replace("import concurrent\n", "from concurrent.futures import ThreadPoolExecutor\n")

# 2. Safe TTS alarm implementation with safe COM uninitialization
old_alarm = """def play_manual_alarm(cam_name):
    try:
        import pythoncom
        pythoncom.CoInitialize() 
        engine = pyttsx3.init()
        engine.say(f"Attention! Security Alert triggered at {cam_name}.")
        engine.runAndWait()
    except Exception: 
        pass"""

new_alarm = """def play_manual_alarm(cam_name):
    if pyttsx3 is None:
        return
    pythoncom_module = None
    com_initialized = False
    try:
        try:
            import pythoncom as pythoncom_module
            pythoncom_module.CoInitialize()
            com_initialized = True
        except ImportError:
            pass
        engine = pyttsx3.init()
        engine.say(f"Attention! Security Alert triggered at {cam_name}.")
        engine.runAndWait()
        try:
            engine.stop()
        except Exception:
            pass
    except Exception as e:
        print(f"TTS alarm error: {e}")
    finally:
        if com_initialized and pythoncom_module is not None:
            try:
                pythoncom_module.CoUninitialize()
            except Exception:
                pass"""

if old_alarm in text:
    text = text.replace(old_alarm, new_alarm)

path.write_text(text, encoding="utf-8")

# Compile check to guarantee zero indentation/syntax errors before Django boots
py_compile.compile(str(path), doraise=True)
print("SUCCESS: core/views.py fixed and compile check passed!")

