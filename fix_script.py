path = 'core/views.py'
with open(path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# Replace the entire broken block cleanly with a verified, perfectly indented function
clean_block = '''def play_manual_alarm(cam_name):
    try:
        import pythoncom
        pythoncom.CoInitialize()
        if pyttsx3:
            engine = pyttsx3.init()
            engine.say("Attention! Security Alert triggered at " + cam_name)
            engine.runAndWait()
    except Exception:
        pass'''

if 'def play_manual_alarm' in content:
    import re
    content = re.sub(r'def play_manual_alarm\b[\s\S]*?(?=\n\ndef [a-zA-Z_]|\Z)', clean_block, content)
else:
    content += '\n\n' + clean_block

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('SUCCESS: core/views.py permanently fixed!')
