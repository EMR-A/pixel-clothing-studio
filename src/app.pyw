# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pixel Clothing Studio contributors
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from desktop import main
if '--self-check' in sys.argv:
    import json
    print(json.dumps({'modernUI':True,'cloudOnly':True,'loopbackOnly':True,'engine':(Path(__file__).resolve().parent.parent/'engine/blender/blender.exe').is_file()}))
else:main()
