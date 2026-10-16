# Profile graphics

`build.py` draws every SVG in `assets/` in the victorstudios.org palette (ink #0b0c10, orange #ff6a00, cream #f7f0dc, indigo #2a1b72) with Geist, Geist Mono and Oxanium embedded, so GitHub renders them exactly.

```bash
pip install fonttools pillow
python3 tools/build.py
```

Edit the `PRODUCTS`, `SERVICES`, `WORK` and `PILLS` lists to change the cards. Source images are read from the local Victor Studios folders.
