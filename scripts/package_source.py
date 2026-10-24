# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pixel Clothing Studio contributors
"""Make a small source archive; never include the installed engine or user outputs."""
from pathlib import Path
import hashlib,json,zipfile
from check_source import ROOT,check

def main():
    files=check();destination=ROOT/'dist';destination.mkdir(exist_ok=True)
    archive=destination/'PixelClothingStudio-Source.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as output:
        for path in files:output.write(path,'pixel-clothing-studio/'+path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(archive) as output:assert output.testzip() is None
    result={'archive':archive.name,'files':len(files),'bytes':archive.stat().st_size,'sha256':hashlib.file_digest(archive.open('rb'),'sha256').hexdigest(),'sourceOnly':True}
    (destination/'source-package.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))

if __name__=='__main__':main()
