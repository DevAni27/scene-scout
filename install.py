#!/usr/bin/env python3
"""Install SceneScout into an existing Hermes profile; never contacts the rig."""
import argparse
from pathlib import Path
import re
import shutil
import tempfile
import time

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--profile',default='liquid-galaxy-agent');a=ap.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+',a.profile):ap.error('Use a profile name, not a filesystem path.')
    profile=Path.home()/'.hermes/profiles'/a.profile
    if not profile.is_dir():ap.error('Existing profile not found: '+str(profile))
    source=Path(__file__).resolve().parent;dest=profile/'skills/liquid-galaxy/scene-scout'
    if source==dest:ap.error('Already inside the installed skill.')
    try:
        from PIL import Image,ImageFont
        ImageFont.truetype(str(source/'assets/DejaVuSans.ttf'),24)
    except ImportError:ap.error('Pillow missing in this Python. On Ubuntu: sudo apt install python3-pil')
    dest.parent.mkdir(parents=True,exist_ok=True)
    temp=Path(tempfile.mkdtemp(prefix='.scene-scout-install-',dir=str(dest.parent)))
    try:
        staged=temp/'scene-scout';shutil.copytree(source,staged,ignore=shutil.ignore_patterns('.git','__pycache__','*.pyc','.env','state','sessions'))
        backup=None
        if dest.exists():
            backup=profile/'backups'/('scene-scout-'+str(time.time_ns()));backup.parent.mkdir(parents=True,exist_ok=True);dest.rename(backup)
        try:staged.rename(dest)
        except OSError:
            if backup:backup.rename(dest)
            raise
        if backup:print('Previous version backed up: '+str(backup))
    finally:shutil.rmtree(temp)
    print('Installed SceneScout: '+str(dest))
    print('Existing rig connection, Classroom and scouting state preserved. No remote changes made.')
    print('Start a fresh Nara chat, or reload the scene-scout skill instructions.')

if __name__=='__main__':main()
