# Publishing source and binary releases

## This source repository

Publish the clean repository tree. Our application code is GPL-3.0-or-later;
preserve `LICENSE`, copyright notices and `THIRD_PARTY_NOTICES.md`. Source ZIPs are
created with `python scripts/package_source.py`. They contain no external runtime,
reader, game content or customer data. Do not upload a working Studio installation
or the parent workspace as the source repository.

The source grant does not turn PyMateria, Rockstar assets or a separate pixel-skin
resource into GPL software. Make that dependency distinction visible in release
notes rather than describing the complete runtime as entirely open source.

## If publishing a portable binary

Use a versioned, clean build and preserve its first-party source together with
build instructions. Before offering a runtime archive:

1. Identify the exact Blender, Sollumz, Python, szio, Pillow and other component
   versions. Retain every bundled component's original licenses and notices.
2. For GPL-covered binaries, satisfy the applicable corresponding-source
   distribution requirements for those exact versions, including any patches and
   required build material. Providing that source alongside the binary release is
   one practical route; verify the selected GPL distribution method. Do not treat
   a general homepage or an unrelated upstream version as corresponding source.
3. PyMateria, its wheel, installed modules and metadata must be absent from all
   uploaded archives. Users handle the separate official reader agreement and
   installation. Do not mirror its installer.
4. Exclude game files, customer images, accounts, upload receipts, configuration
   backups and browser profiles. The source checker applies to source artifacts;
   a binary release needs its own complete dependency and content review.
5. Publish the source identifier, build details and SHA256 digests with the release.
   Use GitHub Releases for large runtime assets instead of committing them to Git.

The local build helper includes our notices and upstream files it copies. It does
not automatically fetch corresponding source or certify every upstream license.
The existing development-machine runtime ZIP is not made release-ready merely by
uploading this new source repository.

References: [GNU GPLv3](https://www.gnu.org/licenses/gpl-3.0.html),
[Blender license](https://www.blender.org/about/license/),
[Sollumz](https://github.com/Sollumz/Sollumz),
[PyMateria agreement](https://static.cfx.re/PyMateria-License-Agreement.pdf),
[GitHub binary releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases).
