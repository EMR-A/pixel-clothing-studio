# Running and building on Windows

## App development

Install a full CPython 3.12 distribution with Tkinter and an installed Edge/Chrome.
Create a virtual environment and install `requirements.txt`, then run `src/app.pyw`
from the repository root. UI assets and translations are plain local files; no
frontend bundling step is needed. `python src/app.pyw --self-check` prints startup
metadata without opening the desktop window.

`engine/` is intentionally ignored. The UI can start without it, but rendering
requires the following local layout:

```text
engine/
  blender/                  # blender.exe, its Python and original license files
  addons/sollumz/            # __init__.py, blender_manifest.toml, LICENSE, etc.
  dependencies/
    szio/                   # compatible with Blender's embedded Python
    szio-*.dist-info/
    PIL/                    # Pillow for Blender's embedded Python
    pillow-*.dist-info/
```

Reference integration: Blender 5.2.2, Sollumz 2.9.0, szio 1.3.0.dev9, Pillow 12.3.0.
These exact binary versions are not supplied by the source repository. Obtain
them from their upstream distributions or an installation you are entitled to use,
and retain the original license and source references. Dependency wheels must
match Blender's embedded Python and platform; app Python 3.12 wheels are not a
substitute for Blender Python 3.13 wheels.

PyMateria is deliberately absent. Its existing user installation may be found by
the app; otherwise first-run setup shows its official agreement, asks for acceptance
and verifies the pinned official download. Do not copy it into a distributable
folder. See the third-party notices for its separate restrictions.

## Local portable build

The build script accepts explicit input folders. It performs no downloads and
does not copy your game, server, project outputs or account data. Replace these
example folders with your own clean component locations:

```powershell
python scripts/build_portable.py `
  --python-dir "C:\Tools\Python312" `
  --blender-dir "C:\Tools\Blender" `
  --sollumz-dir "C:\Tools\Sollumz" `
  --renderer-deps "C:\Tools\BlenderPython313\site-packages" `
  --check
```

After validation, run the same command without `--check`. The default output is
`dist/PixelClothingStudio/`; use `--output dist/AnotherBuild` for a different new
folder. Existing output directories are never overwritten or deleted. If Pillow
is not installed in the Python environment running the build script, supply
`--app-deps` pointing to its app-compatible site-packages.

The launcher is compiled using the Windows .NET Framework C# compiler at
`%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe`. The complete result includes
`source/`, `python/`, `engine/`, license notices and `PixelClothingStudio.exe`.
The script checks startup metadata without opening FiveM or the GUI. This is a
local build, not an assertion that binary publication obligations are complete.

## Tests

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/check_source.py
npm install
npx playwright install chromium
npm run test:ui
```

The 67 Python tests use synthetic temporary files and mocked cloud requests.
Loopback API tests require permission to listen on 127.0.0.1. Optional headless UI
tests cover all 18 languages, RTL, layout, persistence and switching during a task.
Set `BROWSER_EXECUTABLE_PATH` if using an installed Chrome instead of Playwright's
download. These tests do not control the user's active game or browser profile.

## Source archive

```powershell
python scripts/package_source.py
```

This creates `dist/PixelClothingStudio-Source.zip` from a strict source allowlist.
It excludes `.git`, runtimes, screenshots, build outputs, profiles, generated
catalogs and images. A SHA256 manifest is written beside the archive.
