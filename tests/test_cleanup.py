from pathlib import Path
import copy
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import scout_engine as e
e.c=e.rig

class CleanupTests(unittest.TestCase):
 def run_cleanup(self,missing_original=False,external_side=False):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);web=root/'web';backup=root/'backup'
   (web/'kml/scene-scout').mkdir(parents=True);backup.mkdir()
   (backup/'0').write_text('http://lg1:81/original.kml\n')
   (backup/'1').write_bytes(b'ORIGINAL RIGHT')
   if missing_original:(backup/'2.absent').touch()
   else:(backup/'2').write_bytes(b'ORIGINAL LEFT')
   (web/'kml/slave_2.kml').write_text('EXTERNAL NEW PANEL' if external_side else e.c.URL+'/panel.png')
   (web/'kml/slave_3.kml').write_text(e.c.URL+'/branding.png')
   (web/'kmls.txt').write_text('http://lg1:81/original.kml\n'+e.c.URL+'/live.kml\nhttp://lg1:81/added-later.kml\n')
   (web/'kml/scene-scout/scene.kml').write_text('OLD SCENE')
   commands=[]
   class LocalRig:
    def __init__(self,d):pass
    def ssh(self,command,data=None):
     commands.append(command)
     if command=='python3 -':
      self_scene=ET.fromstring((web/'kml/scene-scout/scene.kml').read_bytes())
      if self_scene.findall('.//{'+e.c.K+'}Placemark'):raise AssertionError('Scene not empty before unlink')
     command=command.replace('/var/www/html',str(web)).replace('sleep 3','true')
     if data:data=data.replace(b'/var/www/html',str(web).encode())
     return subprocess.run(['bash','-c',command],input=data,capture_output=True,check=True).stdout.decode().strip()
    def copy(self,paths):
     for p in paths:shutil.copyfile(p,web/'kml/scene-scout'/p.name)
   state=dict(backup=str(backup),backup_files=['/var/www/html/kmls.txt','/var/www/html/kml/slave_2.kml','/var/www/html/kml/slave_3.kml'],records={'one':[{'verdict':'partial','evidence':'Needs help.'}]})
   with patch.object(e.c,'Rig',LocalRig),patch.object(e.c,'connection',return_value={}),patch.object(e,'STATE',root/'state.json'):
    e.c.restore(state)
    self.assertEqual((web/'kmls.txt').read_text(),'http://lg1:81/original.kml\nhttp://lg1:81/added-later.kml\n')
    self.assertEqual((web/'kml/slave_2.kml').read_bytes(),b'EXTERNAL NEW PANEL' if external_side else b'ORIGINAL RIGHT')
    if missing_original:ET.fromstring((web/'kml/slave_3.kml').read_bytes())
    else:self.assertEqual((web/'kml/slave_3.kml').read_bytes(),b'ORIGINAL LEFT')
    self.assertTrue(state['restored']);self.assertEqual(len(state['records']['one']),1)
    e.c.restore(state) # repeat is safe and does not reintroduce links
    self.assertNotIn(e.c.URL,(web/'kmls.txt').read_text())
 def test_empty_scene_before_unlink_and_restore(self):self.run_cleanup()
 def test_preserve_panel_replaced_by_another_app(self):self.run_cleanup(external_side=True)
 def test_missing_original_panel_leaves_valid_empty_kml(self):self.run_cleanup(missing_original=True)

if __name__=='__main__':unittest.main()
