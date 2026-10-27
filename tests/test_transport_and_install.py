import ast
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import scout_engine as e
ROOT=Path(__file__).resolve().parents[1]

class IntegrationTests(unittest.TestCase):
 def test_full_deploy_replace_resume_export_cleanup(self):
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d);web=folder/'web';(web/'kml').mkdir(parents=True)
   (web/'kmls.txt').write_text('http://lg1:81/another-app.kml\n')
   (web/'kml/slave_2.kml').write_text('ORIGINAL RIGHT');(web/'kml/slave_3.kml').write_text('ORIGINAL LEFT')
   remote=web/'kml/scene-scout';scripts=[]
   class LocalRig:
    def __init__(self,profile):self.d=profile
    def ssh(self,command,data=None):
     if command=='hostname':return 'test-lg1'
     if command=='printf "%s" "$HOME"':return str(folder/'remote-home')
     if data and command=='python3 -':
      scripts.append(data.decode());ast.parse(data.decode(),feature_version=(3,5))
     command=command.replace('/var/www/html',str(web)).replace('/tmp/query.txt',str(folder/'query.txt')).replace('sleep 3','true')
     if data:data=data.replace(b'/var/www/html',str(web).encode())
     return subprocess.run(['bash','-c',command],input=data,capture_output=True,check=True).stdout.decode().strip()
    def copy(self,paths):
     for p in paths:shutil.copyfile(p,remote/p.name)
   with patch.object(e,'STATE',folder/'state.json'),patch.object(e.rig,'Rig',LocalRig),patch.object(e.rig,'connection',return_value={'screens':3,'username':'lg'}):
    s=e.initial(e.load_json(ROOT/'references/pune-waterside.json'));e.publish(s)
    self.assertTrue((remote/'pin-0.png').exists());self.assertIn(e.rig.URL,(web/'kmls.txt').read_text())
    s=e.change(e.read(),'show',id='khadakwasla');s=e.change(s,'mark',id='khadakwasla',decision='saved',note='Keep');e.publish(s)
    query=(folder/'query.txt').read_text();self.assertIn('<tilt>75</tilt>',query)
    s=e.replace(e.read(),'pashan',e.load_json(ROOT/'references/replace-pashan.json'));e.publish(s)
    self.assertEqual(e.read()['decisions']['khadakwasla']['status'],'saved');self.assertEqual(e.read()['selected'],'varasgaon')
    (web/'kmls.txt').write_text((web/'kmls.txt').read_text()+'http://lg1:81/later-app.kml\n')
    e.export(s,folder/'export');e.rig.restore(s)
    self.assertEqual((web/'kml/slave_2.kml').read_text(),'ORIGINAL RIGHT');self.assertEqual((web/'kml/slave_3.kml').read_text(),'ORIGINAL LEFT')
    self.assertEqual((web/'kmls.txt').read_text(),'http://lg1:81/another-app.kml\nhttp://lg1:81/later-app.kml\n')
    self.assertFalse(ET.parse(remote/'scene.kml').findall('.//{'+e.rig.K+'}Placemark'))
    self.assertTrue(scripts);self.assertNotIn('time_ns',scripts[0]);self.assertTrue(e.read()['restored'])
 def test_install_preserves_profile_and_backs_up_existing_skill(self):
  spec=importlib.util.spec_from_file_location('scout_install',ROOT/'install.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);profile=p/'.hermes/profiles/liquid-galaxy-agent';(profile/'state').mkdir(parents=True)
   (profile/'state/scene-scout.json').write_text('existing session');(profile/'state/lg-connection.json').write_text('private connection fixture')
   dest=profile/'skills/liquid-galaxy/scene-scout';dest.mkdir(parents=True);(dest/'old.txt').write_text('previous version')
   with patch.object(Path,'home',return_value=p),patch.object(sys,'argv',['install.py']):mod.main()
   self.assertTrue((dest/'SKILL.md').exists());self.assertFalse((dest/'.git').exists());self.assertFalse((dest/'old.txt').exists())
   self.assertEqual((profile/'state/scene-scout.json').read_text(),'existing session');self.assertEqual((profile/'state/lg-connection.json').read_text(),'private connection fixture')
   self.assertTrue(list((profile/'backups').glob('scene-scout-*/old.txt')))

if __name__=='__main__':unittest.main()
