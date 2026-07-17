pyinstaller main.py \
    --onedir \
    --hidden-import PyQt6.QtWebEngineCore \
    --hidden-import PyQt6.QtWebEngineWidgets \
    --add-data "frontend:frontend" \
    --collect-all aicmd

cp -r runtime dist/main/
cp -r models dist/main/
