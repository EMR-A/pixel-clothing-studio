# Pixel Clothing Studio

[Türkçe](docs/README_TR.md) · [Build from source](docs/BUILD.md) ·
[Third-party notices](THIRD_PARTY_NOTICES.md) · [License](LICENSE)

A Windows desktop tool for creating clothing previews for compatible FiveM
`pixel-skin` installations. It renders user-supplied clothing through Blender,
uploads verified images to the user's ImageKit account, and installs image mappings
and the custom CDN address into a selected resource.

This repository contains our application source under **GPL-3.0-or-later**. It does
not contain GTA files, clothing images, API credentials, server resources, Python
or Blender binaries, or PyMateria. **The complete runtime is not entirely open
source:** PyMateria is a separate, restricted reader dependency, governed by its
own agreement. Our license does not grant rights to that dependency or game assets.

## Features

- Transparent 512×512 WebP clothing previews and color/texture variants.
- Full-pack rendering or updates from a single `.ydd` model / `.ytd` texture.
- Existing catalog preservation, resumable work and content-addressed images.
- Upload only new/changed images; verify original bytes before activation.
- Automatic `pixel-skin` integration, backups and rollback on write failure.
- 18 offline languages, Arabic RTL, and light/dark themes.
- Progress, remaining-time estimates and a preview of the latest image.

The UI runs on loopback with a per-run capability token. The ImageKit private key
is used in memory, never saved to the app's state or written into resource files.
Image binaries remain on the CDN; only metadata and a URL are installed locally.

## Run from source

Windows, full CPython 3.12 with Tkinter, and Edge or Chrome are required for the
desktop shell. From the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src\app.pyw
```

The UI can open without the renderer. To generate clothing images, prepare the
local `engine/` layout described in [BUILD.md](docs/BUILD.md), a supported GTA V
Legacy installation and clothing assets you are entitled to process.
The tested renderer uses Blender 5.2.2, Sollumz 2.9.0 and szio 1.3.0.dev9.
These are compatibility references, not a claim that other versions are supported.

## Use

1. Choose a custom clothing resource or its `stream` folder. Extract ZIP/RAR first.
   For a targeted update, select one `.ydd` or `.ytd` file. Related files must be
   discoverable in the same resource. Keep the previous output folder.
2. Generate previews. A model update covers its variants; a texture update covers
   only that variant. Existing clothing and variant mappings are retained.
3. On **Upload to cloud**, choose the server's compatible `pixel-skin` folder,
   containing `fxmanifest.lua`, `shared` and `html`.
4. Use your ImageKit account's `private_` key. In-app instructions explain key
   creation and permissions. Upload and connect; already-uploaded projects can be
   integrated without entering a key or uploading again.
5. Old resource settings are backed up in the output folder's `.pixel-backups/`.
   On a running server, run `restart pixel-skin` when ready. Studio does not restart
   the server or modify player records.

Use one output project and ImageKit account for multiple packs. Do not run two
Studio instances against the same output folder. Integration rejects a CDN change
that would strand preserved mappings. The compatible `pixel-skin` resource itself
is not distributed or licensed by this repository.

## Languages

Türkçe, English, Deutsch, Français, Español, Português (Brasil), Italiano,
Nederlands, Polski, Русский, Українська, العربية, हिन्दी, Bahasa Indonesia,
Tiếng Việt, 简体中文, 日本語 and 한국어.

Language and theme choices are remembered locally. File paths, identifiers and
commands are preserved. Detailed diagnostics from third-party components may be
in English. Translations are in `src/locales.json` and require no translation API.

## Tests

The Python tests generate synthetic fixtures; no GTA assets, real keys, account
access or live server are needed. API tests use a temporary loopback server.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
.\.venv\Scripts\python.exe scripts\check_source.py
```

Optional UI tests need Node.js 20+:

```powershell
npm install
npx playwright install chromium
npm run test:ui
```

To use an installed browser instead, set `BROWSER_EXECUTABLE_PATH` to its executable.
The tests open an isolated headless browser, not the user's FiveM or desktop UI.

## License and distribution

Copyright (C) 2026 Pixel Clothing Studio contributors.
Our code and documentation are licensed under GNU GPL version 3 or, at your option,
any later version; see [LICENSE](LICENSE). Third-party components retain their
own terms. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), including the
separate PyMateria agreement, and [release instructions](docs/RELEASING.md).

Publish this source tree to GitHub, not a whole working directory or installed
runtime. Large portable archives belong in Releases only after their dependency
licenses and corresponding-source requirements are satisfied. No upstream binary
or game asset is included in the source ZIP produced by this repository.
