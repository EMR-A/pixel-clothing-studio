# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pixel Clothing Studio contributors
"""Runtime discovery and first-run setup. No private API credentials are saved."""
import configparser, hashlib, importlib.util, json, os, re, subprocess, sys, urllib.request, zipfile
from pathlib import Path

AGREEMENT='https://static.cfx.re/PyMateria-License-Agreement.pdf'
PYMATERIA_SHA='64f881613c57835c84cf0cd1bc1c4d6e2aa3bac927886d90ccf623e523b365d5'

def game_root():
    ini=Path(os.environ.get('LOCALAPPDATA',''))/'FiveM/FiveM.app/CitizenFX.ini'
    if ini.exists():
        config=configparser.ConfigParser();config.read(ini,encoding='utf-8-sig')
        for section in config.sections():
            value=config.get(section,'IVPath',fallback='')
            if value and (Path(value)/'x64v.rpf').is_file():return value
    try:
        import winreg
        for key in [r'SOFTWARE\Rockstar Games\Grand Theft Auto V',r'SOFTWARE\WOW6432Node\Rockstar Games\Grand Theft Auto V']:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,key) as handle:
                    value=winreg.QueryValueEx(handle,'InstallFolder')[0]
                if (Path(value)/'x64v.rpf').is_file():return value
            except OSError:pass
    except ImportError:pass
    candidate=Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Rockstar Games/Grand Theft Auto V Legacy'
    return str(candidate) if (candidate/'x64v.rpf').is_file() else ''

def existing_pymateria():
    base=Path(os.environ.get('APPDATA',''))/'Blender Foundation/Blender'
    for path in base.glob('5.2/extensions/.user/*/sollumz/lib/python3.13/site-packages'):
        if (path/'pymateria').is_dir():return str(path)
    return ''

def engine_environment(tool_root):
    root=Path(tool_root);env=os.environ.copy()
    env['PYTHONNOUSERSITE']='1'
    env['BLENDER_USER_CONFIG']=str(root/'state/blender-config')
    paths=[root/'engine/dependencies']
    installed=existing_pymateria()
    if installed:
        paths.append(Path(installed));env['PIXEL_PYMATERIA_PATH']=installed
    env['PYTHONPATH']=os.pathsep.join(map(str,paths))
    return env

def has_pymateria(root):
    return (Path(root)/'engine/dependencies/pymateria').is_dir() or bool(existing_pymateria())

def install_pymateria(root):
    """Called only after the customer's explicit first-run agreement action."""
    root=Path(root);target=root/'engine/dependencies';target.mkdir(parents=True,exist_ok=True)
    with urllib.request.urlopen('https://static.cfx.re/whl/pymateria/',timeout=30) as response:
        page=response.read().decode()
    from urllib.parse import urljoin
    links=re.findall(r'href=[\"\']([^\"\']+)[\"\']',page)
    relative=next((x for x in links if 'pymateria-0.2.0-cp313-cp313-win_amd64.whl' in x),None)
    if not relative:raise RuntimeError('Resmi PyMateria dağıtım dosyası bulunamadı.')
    url=urljoin('https://static.cfx.re/whl/pymateria/',relative).split('#')[0]
    if not url.startswith('https://static.cfx.re/'):raise RuntimeError('Beklenmeyen kurulum kaynağı.')
    with urllib.request.urlopen(url,timeout=90) as response:data=response.read(50*1024*1024)
    if hashlib.sha256(data).hexdigest()!=PYMATERIA_SHA:raise RuntimeError('Motor bileşeni beklenen SHA256 ile eşleşmiyor.')
    import io
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for member in archive.infolist():
            if not (target/member.filename).resolve().is_relative_to(target.resolve()):raise RuntimeError('Geçersiz arşiv yolu.')
        archive.extractall(target)
    return 'Gerekli bileşen resmi kaynaktan kuruldu.'
