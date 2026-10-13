"""Extract Office fonts for export_pptx_office.py; run in the copied build directory.
usage: python3 prepare_pptx_fonts.py [PowerPoint-DFonts-directory]
The files stay in cache/fonts_office; do not install or modify system fonts.
"""
from pathlib import Path
from fontTools.ttLib import TTFont
import sys
ROOT = Path(__file__).resolve().parent
src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/Applications/Microsoft PowerPoint.app/Contents/Resources/DFonts")
sources = {"yahei": "msyh.ttc", "yahei_bold": "msyhbd.ttc", "consolas": "Consola.ttf", "consolas_bold": "Consolab.ttf"}
for name in sources.values():
    if not (src / name).is_file():
        raise SystemExit(f"Office font missing: {src / name}")
out = ROOT / "cache" / "fonts_office"
out.mkdir(parents=True, exist_ok=True)
for dst, name in sources.items():
    f = TTFont(src / name, fontNumber=0)
    if "prep" in f and not f["prep"].program.getBytecode():
        del f["prep"]   # Chrome OTS rejects the empty Consolas prep table
    path = out / (dst + ".ttf")
    f.save(path)
    f.close()
    print(path)
