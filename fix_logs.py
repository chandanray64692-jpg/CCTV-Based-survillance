
path = "core/views.py"
with open(path, "r", encoding="utf-8", errors="ignore") as f:
    content = f.read()

content = content.replace("if status_level != \"Info\":", "if True:")

with open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write(content)

print("SUCCESS: Log filter updated successfully!")

