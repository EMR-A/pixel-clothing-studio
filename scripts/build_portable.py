# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pixel Clothing Studio contributors
"""Build a local Windows runtime from explicit, separately obtained components."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,sys,sysconfig,tomllib

ROOT=Path(__file__).resolve().parents[1]
GAME_EXTENSIONS={'.ydd','.ytd','.yft','.ydr','.ybn','.rpf'}

def forbidden(path):
    return any(part.lower()=='pymateria' or part.lower().startswith(('pymateria-','pymateria.')) for part in path.parts) or path.suffix.lower() in GAME_EXTENSIONS

def required(path):
    if not path.exists():raise ValueError('Required component missing: '+str(path))
    return path

def package_info(folder,prefix):
    choices=list(folder.glob(prefix+'-*.dist-info'))
    if len(choices)!=1:raise ValueError('Expected one '+prefix+' .dist-info directory in '+str(folder))
    return choices[0]

def io_path(path):
    absolute=str(Path(path).absolute())
    if os.name!='nt' or absolute.startswith('\\\\?\\'):return Path(absolute)
    return Path('\\\\?\\UNC\\'+absolute[2:] if absolute.startswith('\\\\') else '\\\\?\\'+absolute)

def copy_tree(source,destination,exclude=()):
    shutil.copytree(io_path(source),io_path(destination),ignore=shutil.ignore_patterns('__pycache__','*.pyc','.git','state','logs','*.blend1',*exclude))

def validate(args):
    python=Path(args.python_dir).resolve();blender=Path(args.blender_dir).resolve()
    addon=Path(args.sollumz_dir).resolve();deps=Path(args.renderer_deps).resolve();app_deps=Path(args.app_deps).resolve()
    for name in ['python.exe','pythonw.exe','Lib','DLLs','tcl','LICENSE.txt']:required(python/name)
    required(blender/'blender.exe')
    for name in ['blender_manifest.toml','__init__.py','LICENSE']:required(addon/name)
    for folder in [deps,app_deps]:required(folder/'PIL');package_info(folder,'pillow')
    required(deps/'szio');package_info(deps,'szio')
    for folder in [blender,addon,deps]:
        for path in folder.rglob('*'):
            if path.is_file() and forbidden(path):raise ValueError('A restricted reader or game asset was found; choose clean component folders: '+str(path))
    return python,blender,addon,deps,app_deps

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python-dir',default=sys.base_prefix,help='Full Windows CPython installation with Tkinter')
    parser.add_argument('--blender-dir',required=True)
    parser.add_argument('--sollumz-dir',required=True)
    parser.add_argument('--renderer-deps',required=True,help='Blender-compatible szio and Pillow site-packages')
    parser.add_argument('--app-deps',default=sysconfig.get_paths()['purelib'],help='Application Pillow site-packages')
    parser.add_argument('--output',default=str(ROOT/'dist/PixelClothingStudio'))
    parser.add_argument('--check',action='store_true',help='Validate inputs without copying or compiling')
    args=parser.parse_args();python,blender,addon,deps,app_deps=validate(args)
    output=Path(args.output).resolve();dist=(ROOT/'dist').resolve()
    if not output.is_relative_to(dist) or output==dist:raise ValueError('Output must be a new directory beneath this repository’s dist/.')
    if output.exists():raise ValueError('Output already exists. Choose another directory; existing files will not be overwritten.')
    if args.check:
        print(json.dumps({'inputsValid':True,'containsPyMateria':False,'mode':'validation only'}));return
    if os.name!='nt':raise ValueError('The portable Windows launcher must be built on Windows.')
    compiler=Path(os.environ.get('WINDIR','C:/Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe';required(compiler)
    output.mkdir(parents=True)
    copy_tree(ROOT/'src',output/'source');copy_tree(blender,output/'engine/blender');copy_tree(addon,output/'engine/addons/sollumz')
    for package in ['szio','PIL']:copy_tree(deps/package,output/'engine/dependencies'/package)
    for prefix in ['szio','pillow']:
        info=package_info(deps,prefix);copy_tree(info,output/'engine/dependencies'/info.name)
    runtime=output/'python';runtime.mkdir()
    for folder in ['Lib','DLLs','tcl']:
        copy_tree(python/folder,runtime/folder,('site-packages','test','tests'))
    for path in python.iterdir():
        if path.is_file() and path.suffix.lower() in ['.exe','.dll','.txt']:shutil.copy2(path,runtime/path.name)
    copy_tree(app_deps/'PIL',runtime/'Lib/site-packages/PIL')
    info=package_info(app_deps,'pillow');copy_tree(info,runtime/'Lib/site-packages'/info.name)
    for path in [ROOT/'LICENSE',ROOT/'THIRD_PARTY_NOTICES.md',ROOT/'README.md',ROOT/'docs/README_TR.md']:
        shutil.copy2(path,output/path.name)
    copy_tree(ROOT/'licenses',output/'licenses')
    subprocess.run([str(compiler),'/nologo','/target:winexe','/reference:System.Windows.Forms.dll','/out:'+str(output/'PixelClothingStudio.exe'),str(ROOT/'src/Launcher.cs')],check=True)
    assert not any(forbidden(p) for p in io_path(output).rglob('*') if p.is_file())
    # The subprocess tests only startup metadata; it does not open the GUI or game.
    subprocess.run([str(runtime/'python.exe'),str(output/'source/app.pyw'),'--self-check'],check=True)
    manifest=tomllib.loads((addon/'blender_manifest.toml').read_text('utf-8'))
    info={'sollumzVersion':manifest.get('version'),'containsPyMateria':False,'sourceLicense':'GPL-3.0-or-later','localBuildOnly':True,'sourceSha256':{p.relative_to(ROOT/'src').as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'src').rglob('*') if p.is_file() and '__pycache__' not in p.parts}}
    (output/'build-info.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
    print('Local build complete. Read docs/RELEASING.md before distributing binaries.')

if __name__=='__main__':main()
