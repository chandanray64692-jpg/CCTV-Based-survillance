path = 'core/views.py'
with open(path, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if 'def play_manual_alarm' in line:
        skip = True
        continue
    if skip:
        if line.startswith('def ') or line.startswith('@') or line.startswith('# ='):
            skip = False
    if not skip:
        new_lines.append(line)

clean_func = '\n\ndef play_manual_alarm(cam_name):\n    try:\n        import pythoncom\n        pythoncom.CoInitialize()\n        if pyttsx3:\n            engine = pyttsx3.init()\n            engine.say("Attention! Security Alert triggered at " + cam_name)\n            engine.runAndWait()\n    except Exception:\n        pass\n'

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
    f.write(clean_func)

print('SUCCESS: play_manual_alarm fixed cleanly!')
