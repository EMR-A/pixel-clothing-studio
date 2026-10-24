# Licensing scope and third-party notices

The root `LICENSE` and the SPDX notices apply to code and documentation authored
for Pixel Clothing Studio. They do not relicense third-party software, game files,
customer clothing packs, generated images, trademarks or a separate pixel-skin
resource. This source repository vendors no runtime or third-party implementation.

## Runtime components

| Component | Tested version | License / source | Distribution in this source tree |
|---|---|---|---|
| Blender | 5.2.2 | [GNU GPL; binary distributions GPL-3.0-or-later compatible](https://www.blender.org/about/license/), [source](https://projects.blender.org/blender/blender) | Not included |
| Sollumz | 2.9.0 | GPL-3.0-or-later; copyright 2020–2025 Skylumz, Colton and alexguirre; [source and license](https://github.com/Sollumz/Sollumz) | Not included |
| szio | 1.3.0.dev9 | MIT; copyright 2025 Sollumz contributors; [source](https://github.com/Sollumz/szio) | License text only: `licenses/szio-MIT.txt` |
| CPython | 3.12 app; Blender embeds its own Python | Python Software Foundation license and accompanying notices; [source](https://github.com/python/cpython) | License text only: `licenses/Python.txt` |
| Pillow | 12.3.0 reference; app supports >=10.4,<13 | MIT-CMU / accompanying notices; [source](https://github.com/python-pillow/Pillow) | License text only: `licenses/Pillow.txt` |
| NumPy and Blender's other libraries | Supplied by the chosen Blender runtime | Their individual licenses and notices in that runtime | Not included |
| Playwright | 1.62.1, optional tests | Apache-2.0; [source](https://github.com/microsoft/playwright) | Not included; development dependency only |
| Edge / Chrome | Installed by the user | Browser vendor's terms | Not included |
| PyMateria | Reader reference 0.2.0 for Blender Python 3.13 | [Separate proprietary agreement](https://static.cfx.re/PyMateria-License-Agreement.pdf) | **Not included and not covered by our GPL grant** |

The tested versions identify the existing integration, not bundled copies or a
promise of compatibility with future releases. When changing a component version,
review and preserve the license files from that exact distribution.

## PyMateria

PyMateria is not open source. Its agreement restricts redistribution, bundling,
modification and sublicensing. Do not commit or put its wheel, installed package,
binary modules or metadata into a Studio release. Our GPL license does not grant
any PyMateria rights or remove its restrictions.

`src/runtime_setup.py` may locate an existing user installation, or offer the
official agreement and install the official package only after the user accepts.
The official download's pinned SHA256 is checked. Do not replace this with a
redistributed or mirrored copy. Users and distributors remain responsible for
their own permissions and compliance with the applicable third-party terms.

## Game and customer assets

GTA/Rockstar content is not licensed by this repository. Neither ownership nor
permission to redistribute source assets or rendered images is granted here.
The program is for processing supported assets the user is entitled to use.
ImageKit account use is governed by ImageKit's terms and the account owner's quota.

## Binary releases

This source tree has no Blender/Sollumz/CPython binaries. A maintainer distributing
a portable build must retain each component's exact notices, fulfill applicable
GPL corresponding-source obligations and document which files use which licenses.
An ordinary homepage link is not presented here as a blanket substitute for those
obligations. Follow `docs/RELEASING.md` before publishing binary assets.
