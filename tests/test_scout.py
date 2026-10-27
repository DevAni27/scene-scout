import copy
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

class ScoutTests(unittest.TestCase):
 def setUp(self):
  self.plan=e.load_json(ROOT/'references/pune-waterside.json');self.s=e.initial(self.plan)
  self.replacement=e.load_json(ROOT/'references/replace-pashan.json')
 def test_starts_inside_first_location_not_overview(self):
  self.assertEqual(self.s['view'],'location');self.assertEqual(self.s['selected'],self.plan['candidates'][0]['id'])
  self.assertEqual(e.view_values(self.s)['range'],350);self.assertEqual(e.view_values(self.s)['tilt'],75)
 def test_old_wide_plan_uses_close_default_but_explicit_wider_works(self):
  self.s['candidates'][0]['camera']['range']=3000
  self.s['candidates'][0]['camera']['tilt']=50
  self.assertEqual(e.view_values(self.s)['range'],350)
  self.assertEqual(e.view_values(self.s)['tilt'],75)
  adjusted=e.camera_change(self.s,range=1600,tilt=55)
  self.assertEqual(e.view_values(adjusted)['range'],1600);self.assertEqual(e.view_values(adjusted)['tilt'],55)
 def test_diagnostics_are_readonly_and_old_python_compatible(self):
  import ast
  import scout_diagnostics as diag
  source=diag.REMOTE_CHECK.replace('RIGHT','2').replace('LEFT','3')
  ast.parse(source,feature_version=(3,5))
  self.assertNotIn('.write_',source);self.assertNotIn('time_ns',source)
 def test_reference_valid(self):self.assertIs(e.validate(self.plan),self.plan)
 def test_no_fake_three_candidate_padding(self):
  self.plan['candidates'].pop()
  with self.assertRaises(ValueError):e.validate(self.plan)
 def test_source_required(self):
  self.plan['candidates'][0]['facts'][0]['source_ids']=['invented']
  with self.assertRaises(ValueError):e.validate(self.plan)
 def test_no_credential_url(self):
  self.plan['sources'][0]['url']='https://user:secret@example.com'
  with self.assertRaises(ValueError):e.validate(self.plan)
 def test_invalid_latitude(self):
  self.plan['candidates'][0]['coordinates'][1]=90
  with self.assertRaises(ValueError):e.validate(self.plan)
 def test_nonfinite_coordinate(self):
  self.plan['candidates'][0]['coordinates'][0]=float('nan')
  with self.assertRaises(ValueError):e.validate(self.plan)
 def test_outside_radius(self):
  self.plan['candidates'][0]['coordinates']=[0,0]
  with self.assertRaises(ValueError):e.validate(self.plan)
 def test_documented_permission_requires_source(self):
  self.plan['candidates'][0]['practical']['permission']['status']='documented'
  with self.assertRaises(ValueError):e.validate(self.plan)
 def test_missing_criterion(self):
  self.plan['candidates'][0]['criteria'].pop('water')
  with self.assertRaises(ValueError):e.validate(self.plan)
 def test_camera_avoids_topdown(self):
  s=e.change(self.s,'show',id='khadakwasla');v=e.view_values(s)
  self.assertGreaterEqual(v['tilt'],75);self.assertLessEqual(v['range'],350)
  root=ET.fromstring(e.camera_xml(s));self.assertEqual(root.tag,'LookAt');self.assertEqual(root.findtext('altitudeMode'),'relativeToGround')
 def test_adjust_camera_preserves_decisions(self):
  s=e.change(self.s,'show',id='khadakwasla');v=e.camera_change(s,range=450,tilt=72,heading=120)
  self.assertEqual(e.view_values(v)['range'],450);self.assertEqual(v['decisions'],s['decisions'])
 def test_reject_camera_underterrain_risk(self):
  s=e.change(self.s,'show',id='khadakwasla')
  with self.assertRaises(ValueError):e.camera_change(s,range=5)
 def test_show_clears_previous_camera_override(self):
  s=e.camera_change(e.change(self.s,'show',id='pashan'),range=400);s=e.change(s,'next')
  self.assertNotIn('camera_override',s)
 def test_navigation_cycle(self):
  s=self.s
  for i in range(3):s=e.change(s,'next')
  self.assertEqual(s['selected'],self.s['selected'])
 def test_compare_distinct(self):
  with self.assertRaises(ValueError):e.change(self.s,'compare',ids=['pashan','pashan'])
 def test_save_then_replace_other_preserves_saved(self):
  s=e.change(self.s,'mark',id='khadakwasla',decision='saved',note='Keep water and structure')
  saved=copy.deepcopy(e.candidate(s,'khadakwasla'));s=e.replace(s,'pashan',self.replacement)
  self.assertEqual(e.candidate(s,'khadakwasla'),saved);self.assertEqual(s['decisions']['khadakwasla']['status'],'saved')
  self.assertEqual(s['candidates'][1]['id'],'varasgaon');self.assertEqual(s['archived'][0]['candidate']['id'],'pashan')
 def test_saved_replacement_requires_explicit_override(self):
  s=e.change(self.s,'mark',id='pashan',decision='saved')
  with self.assertRaises(ValueError):e.replace(s,'pashan',self.replacement)
  self.assertEqual(e.replace(s,'pashan',self.replacement,allow_saved=True)['selected'],'varasgaon')
 def test_failed_replacement_does_not_mutate(self):
  before=copy.deepcopy(self.s);self.replacement['candidate']['coordinates']=[0,0]
  with self.assertRaises(ValueError):e.replace(self.s,'pashan',self.replacement)
  self.assertEqual(self.s,before)
 def test_brief_change_flags_retained_candidates(self):
  b=copy.deepcopy(self.s['brief']);b['summary']='Prefer greener backgrounds now.'
  s=e.replace(self.s,'pashan',self.replacement,b)
  self.assertTrue(e.candidate(s,'khadakwasla')['fit_review_required']);self.assertEqual(e.candidate(s,'khadakwasla')['criteria']['green']['status'],'unknown')
  self.assertFalse(e.candidate(s,'varasgaon').get('fit_review_required',False))
 def test_new_required_criterion_unknown_for_retained(self):
  b=copy.deepcopy(self.s['brief']);b['criteria'].append({'id':'crowds','label':'Low foot traffic','priority':'prefer'})
  self.replacement['candidate']['criteria']['crowds']={'status':'unknown','reason':'Check on site','source_ids':[]}
  s=e.replace(self.s,'pashan',self.replacement,b);self.assertEqual(e.candidate(s,'khadakwasla')['criteria']['crowds']['status'],'unknown')
 def test_source_collision(self):
  self.replacement['sources'][0]['id']='pune-district'
  with self.assertRaises(ValueError):e.replace(self.s,'pashan',self.replacement)
 def test_duplicate_candidate_id(self):
  self.replacement['candidate']['id']='panshet'
  with self.assertRaises(ValueError):e.replace(self.s,'pashan',self.replacement)
 def test_reassessment_cannot_change_location(self):
  with self.assertRaises(ValueError):e.reassess(self.s,'pashan',{'coordinates':[1,2]})
 def test_ended_session_stays_ended(self):
  self.s['ended']=True
  with self.assertRaises(ValueError):e.change(self.s,'overview')
  with self.assertRaises(ValueError):e.replace(self.s,'pashan',self.replacement)
 def test_scene_geometry_small_and_correct(self):
  s=e.change(self.s,'show',id='pashan');root=ET.fromstring(e.geometry(s));ns={'k':e.rig.K}
  self.assertEqual(len(root.findall('.//k:Point',ns)),1)
  xyz=root.find('.//k:Point/k:coordinates',ns).text;self.assertTrue(xyz.startswith('73.785717,18.533752'))
  self.assertIn('scene-scout/pin-1.png',e.geometry(s).decode())
 def test_overlay_aspect_and_refresh(self):
  root=ET.fromstring(e.rig.overlay('http://lg1:81/p.png'));ns={'k':e.rig.K}
  self.assertEqual(root.find('.//k:size',ns).get('y'),'0')
  self.assertEqual(ET.fromstring(e.rig.networklink()).find('.//k:refreshInterval',ns).text,'2')
 def test_every_view_and_replacement_renders(self):
  with tempfile.TemporaryDirectory() as folder:
   states=[e.change(self.s,'overview')]+[e.change(self.s,'show',id=c['id']) for c in self.s['candidates']]+[e.change(self.s,'compare',ids=[c['id'] for c in self.s['candidates']]),e.replace(self.s,'pashan',self.replacement)]
   from PIL import Image
   for i,s in enumerate(states):
    p=e.render(s,Path(folder)/str(i))
    with Image.open(p/'panel.png') as im:self.assertEqual(im.size,(1920,1080))
    ET.parse(p/'scene.kml')
 def test_six_criteria_three_way_comparison(self):
  for i in range(3):
   k='extra-'+str(i);self.s['brief']['criteria'].append({'id':k,'label':'Additional practical condition','priority':'prefer'})
   for c in self.s['candidates']:c['criteria'][k]={'status':'unknown','reason':'Verify','source_ids':[]}
  with tempfile.TemporaryDirectory() as d:e.render(e.change(self.s,'compare',ids=['khadakwasla','pashan','panshet']),Path(d))
 def test_report_keeps_unknowns_decisions_and_source_dates(self):
  s=e.change(self.s,'mark',id='pashan',decision='rejected',note='Too urban for this brief')
  with tempfile.TemporaryDirectory() as folder:
   p=e.export(s,folder);report=(p/'scouting-report.md').read_text()
   self.assertIn('Too urban',report);self.assertIn('permission: unknown',report);self.assertIn('2026-10-27',report)
   self.assertEqual(len(json.loads((p/'shortlist.geojson').read_text())['features']),3)
 def test_report_escapes_injected_html(self):
  self.s['decisions']['pashan']['note']='<script>alert(1)</script>'
  with tempfile.TemporaryDirectory() as folder:
   e.export(self.s,folder);self.assertNotIn('<script>',(Path(folder)/'scouting-report.html').read_text())
 def test_persistence_private_and_resume(self):
  with tempfile.TemporaryDirectory() as d,patch.object(e,'STATE',Path(d)/'state.json'):
   e.save(self.s);self.assertEqual(e.read()['selected'],self.s['selected']);self.assertEqual(e.STATE.stat().st_mode&0o777,0o600)
 def test_layout_failure_does_not_touch_remote(self):
  with patch.object(e,'render',side_effect=ValueError('Too long')),patch.object(e.rig,'connection') as c:
   with self.assertRaises(ValueError):e.publish(self.s)
   c.assert_not_called()
 def test_deployment_failure_retains_pending_intent(self):
  with tempfile.TemporaryDirectory() as d,patch.object(e,'STATE',Path(d)/'state.json'),patch.object(e.rig,'connection',side_effect=RuntimeError('offline')):
   with self.assertRaises(RuntimeError):e.publish(self.s)
   self.assertTrue(e.read()['pending_display']);self.assertEqual(e.read()['brief'],self.s['brief'])
 def test_missing_photo_fails_before_deployment(self):
  self.s['candidates'][0]['photo']={'path':'/missing/image.jpg','credit':'Owner','usage':'Permission','source_id':'pune-district'}
  with self.assertRaises(ValueError):e.import_photos(self.s)
 def test_local_photo_import_and_render(self):
  from PIL import Image
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);Image.new('RGB',(500,300),'#435d65').save(p/'photo.jpg')
   self.s['candidates'][0]['photo']={'path':str(p/'photo.jpg'),'credit':'Test-generated image; not location evidence','usage':'Test fixture only','source_id':'pune-district'}
   with patch.object(e.rig,'HOME',p):
    s=e.import_photos(self.s);e.render(e.change(s,'show',id='khadakwasla'),p/'render')
    self.assertNotEqual(s['candidates'][0]['photo']['path'],str(p/'photo.jpg'))

if __name__=='__main__':unittest.main()
