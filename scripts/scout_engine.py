#!/usr/bin/env python3
"""SceneScout: sourced scouting plans, persistent decisions, close LG views. No AI API calls."""
import argparse
import copy
import datetime as dt
import html
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import lg_transport as rig

ROOT=Path(__file__).resolve().parents[1]
STATE=rig.HOME/'state/scene-scout.json'
PALETTE=['#75ddd1','#edbc7a','#b6a2f0']
DECISIONS=('considering','saved','rejected')

def need(ok,message):
    if not ok:raise ValueError(message)

def text(value,label,limit=240):
    need(isinstance(value,str) and bool(value.strip()) and len(value)<=limit,label+' must be non-empty text, maximum '+str(limit)+' characters')
    need(not any(ord(c)<32 and c not in '\n\t' for c in value),label+' contains control characters')
    return value

def number(v,label,lo,hi):
    need(type(v) in (int,float) and math.isfinite(v) and lo<=v<=hi,label+' outside allowed range')
    return v

def coordinate(v):
    need(isinstance(v,list) and len(v)==2,'Coordinates must be [longitude, latitude]')
    number(v[0],'longitude',-180,180);number(v[1],'latitude',-80,80)

def https(v):
    text(v,'source URL',1400);u=urlparse(v)
    need(u.scheme=='https' and bool(u.hostname) and not u.username and not u.password,'Use a public HTTPS source URL without credentials')
    need(u.hostname not in ('localhost','127.0.0.1','::1') and '.' in u.hostname,'Use a public source hostname')

def distance(a,b):
    x1,y1,x2,y2=map(math.radians,[a[0],a[1],b[0],b[1]])
    h=math.sin((y2-y1)/2)**2+math.cos(y1)*math.cos(y2)*math.sin((x2-x1)/2)**2
    return 6371*2*math.asin(math.sqrt(min(1,max(0,h))))

def validate_sources(sources):
    need(isinstance(sources,list) and 1<=len(sources)<=30,'Use 1–30 actually-read sources')
    ids=set()
    for s in sources:
        text(s.get('id'),'source.id',50);need(re.fullmatch(r'[a-z0-9-]+',s['id']) is not None,'Source IDs use lowercase letters, numbers and hyphens')
        need(s['id'] not in ids,'Duplicate source ID');ids.add(s['id'])
        text(s.get('title'),'source.title',140);https(s.get('url'))
        text(s.get('supports'),'source.supports',380)
        try:dt.date.fromisoformat(s.get('accessed',''))
        except (ValueError,TypeError):raise ValueError('source.accessed must be YYYY-MM-DD')
    return ids

def refs(v,ids,required=True):
    need(isinstance(v,list) and len(v)<=8 and (bool(v) or not required),'Provide source_ids for documented evidence')
    need(all(isinstance(x,str) and x in ids for x in v),'Unknown source ID')

def validate_brief(b):
    need(isinstance(b,dict),'brief must be an object')
    for k,limit in [('title',85),('city',80),('summary',300)]:text(b.get(k),'brief.'+k,limit)
    coordinate(b.get('origin'));number(b.get('radius_km'),'radius_km',1,200)
    criteria=b.get('criteria');need(isinstance(criteria,list) and 1<=len(criteria)<=6,'Use 1–6 criteria')
    ids=[]
    for c in criteria:
        text(c.get('id'),'criterion.id',35);need(re.fullmatch(r'[a-z0-9-]+',c['id']) is not None,'Invalid criterion ID')
        text(c.get('label'),'criterion.label',80);need(c.get('priority') in ('must','prefer','avoid'),'priority must be must, prefer or avoid');ids.append(c['id'])
    need(len(set(ids))==len(ids),'Duplicate criterion ID')
    return b

def validate_candidate(c,b,ids):
    need(isinstance(c,dict),'candidate must be an object')
    text(c.get('id'),'candidate.id',45);need(re.fullmatch(r'[a-z0-9-]+',c['id']) is not None,'Invalid candidate ID')
    text(c.get('name'),'candidate.name',85);coordinate(c.get('coordinates'))
    need(c.get('coordinate_source_id') in ids,'Coordinates need a source ID')
    need(c.get('coordinate_precision') in ('area','site'),'Declare coordinates as area or site')
    need(distance(b['origin'],c['coordinates'])<=b['radius_km'],'Candidate is outside the requested straight-line search radius')
    text(c.get('creative_fit'),'creative_fit',300);text(c.get('tradeoffs'),'tradeoffs',260)
    facts=c.get('facts');need(isinstance(facts,list) and 1<=len(facts)<=4,'Use 1–4 concise sourced facts')
    for f in facts:text(f.get('text'),'fact',220);refs(f.get('source_ids'),ids)
    checks=c.get('checks');need(isinstance(checks,list) and 1<=len(checks)<=5,'Use 1–5 on-site checks')
    for x in checks:text(x,'check',140)
    practical=c.get('practical');need(isinstance(practical,dict),'practical must be an object')
    for k in ('access','facilities','permission'):
        v=practical.get(k);need(isinstance(v,dict),'practical.'+k+' missing')
        need(v.get('status') in ('documented','unknown'),'Evidence status must be documented or unknown')
        text(v.get('text'),k,180);refs(v.get('source_ids'),ids,v['status']=='documented')
    ratings=c.get('criteria');need(isinstance(ratings,dict) and set(ratings)=={x['id'] for x in b['criteria']},'Rate every current criterion, using its ID')
    for v in ratings.values():
        need(isinstance(v,dict) and v.get('status') in ('meets','partial','conflicts','unknown'),'Invalid criterion status')
        text(v.get('reason'),'criterion.reason',160);refs(v.get('source_ids'),ids,v['status']!='unknown')
    camera=c.get('camera',{})
    for k,lo,hi in [('range',50,3500),('tilt',50,78),('heading',0,360)]:
        if k in camera:number(camera[k],'camera.'+k,lo,hi)
    if 'target' in camera:
        coordinate(camera['target']);need(distance(camera['target'],c['coordinates'])<=2,'Camera target must be within 2 km of the candidate')
    if 'photo' in c:
        p=c['photo'];need(isinstance(p,dict),'photo must be an object')
        for k,limit in [('path',1000),('credit',140),('usage',200)]:text(p.get(k),'photo.'+k,limit)
        need(Path(p['path']).is_absolute(),'photo.path must be absolute')
        need(p.get('source_id') in ids,'Photo needs a source reference')
    return c

def validate(plan):
    need(isinstance(plan,dict) and plan.get('schema_version')==1,'schema_version must be 1')
    b=validate_brief(plan.get('brief'));ids=validate_sources(plan.get('sources'))
    cs=plan.get('candidates');need(isinstance(cs,list) and len(cs)==3,'An initial shortlist contains exactly three real candidates')
    seen=set()
    for c in cs:
        validate_candidate(c,b,ids);need(c['id'] not in seen,'Candidate IDs must be unique');seen.add(c['id'])
    return plan

def load_json(path):
    p=Path(path).expanduser();need(p.is_file() and p.stat().st_size<=2_000_000,'JSON file missing or larger than 2 MB')
    return json.loads(p.read_text(encoding='utf-8'))

def save(s):
    STATE.parent.mkdir(parents=True,exist_ok=True)
    p=STATE.with_suffix('.tmp');p.write_text(json.dumps(s,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');os.chmod(p,0o600);p.replace(STATE)

def read():
    need(STATE.exists(),'No scouting session. Start with a researched plan.')
    return json.loads(STATE.read_text(encoding='utf-8'))

rig.save_state=save

def initial(plan,voice=False):
    validate(plan)
    return dict(schema_version=1,session_id=str(time.time_ns()),brief=copy.deepcopy(plan['brief']),sources=copy.deepcopy(plan['sources']),
                candidates=copy.deepcopy(plan['candidates']),decisions={c['id']:{'status':'considering','note':''} for c in plan['candidates']},
                archived=[],history=[],view='location',selected=plan['candidates'][0]['id'],comparison=[],voice=voice,stage='location',ended=False)

def candidate(s,id=None):
    id=id or s['selected']
    for c in s['candidates']:
        if c['id']==id:return c
    raise ValueError('Unknown candidate ID: '+str(id))

def new_history(s,action,detail):
    s['history'].append({'at':dt.datetime.now(dt.timezone.utc).isoformat(),'action':action,'detail':detail})

def change(s,action,id=None,decision=None,note='',ids=None):
    need(not s.get('ended'),'This session ended. Start a new plan; export remains available.')
    s=copy.deepcopy(s)
    if action=='show':candidate(s,id);s.update(view='location',selected=id);s.pop('camera_override',None)
    elif action=='overview':s['view']='overview';s.pop('camera_override',None)
    elif action=='next':
        cs=s['candidates'];i=next(i for i,c in enumerate(cs) if c['id']==s['selected']);s.update(view='location',selected=cs[(i+1)%len(cs)]['id']);s.pop('camera_override',None)
    elif action=='compare':
        need(ids and 2<=len(ids)<=3 and len(set(ids))==len(ids),'Compare 2–3 distinct candidate IDs')
        for x in ids:candidate(s,x)
        s.update(view='compare',comparison=ids);s.pop('camera_override',None)
    elif action=='mark':
        candidate(s,id);need(decision in DECISIONS,'Unknown decision');need(isinstance(note,str) and len(note)<=300,'Note too long')
        s['decisions'][id]={'status':decision,'note':note}
    new_history(s,action,{'id':id,'decision':decision,'note':note,'ids':ids})
    s['stage']=s['view'];return s

def replace(s,id,payload,brief=None,allow_saved=False):
    need(not s.get('ended'),'Session ended')
    s=copy.deepcopy(s);old=candidate(s,id)
    need(s['decisions'][id]['status']!='saved' or allow_saved,'Saved candidate protected. Use --allow-saved only on explicit user request.')
    need(isinstance(payload,dict) and 'candidate' in payload and 'sources' in payload,'Replacement JSON needs candidate and sources')
    all_sources={x['id']:x for x in s['sources']}
    for src in payload['sources']:
        if src['id'] in all_sources:need(all_sources[src['id']]==src,'Source ID collision; give the new source a distinct ID')
        all_sources[src['id']]=src
    source_list=list(all_sources.values());valid_ids=validate_sources(source_list)
    b=validate_brief(brief or s['brief']);c=copy.deepcopy(payload['candidate']);validate_candidate(c,b,valid_ids)
    need(c['id'] not in {x['id'] for x in s['candidates']},'Replacement needs a new candidate ID, preserving history')
    s['archived'].append({'candidate':old,'decision':s['decisions'][id],'brief':copy.deepcopy(s['brief'])})
    slot=s['candidates'].index(old);s['candidates'][slot]=c;s['decisions'][c['id']]={'status':'considering','note':''};s['decisions'].pop(id)
    if b!=s['brief']:
        for other in s['candidates']:
            if other['id']==c['id']:continue
            other['fit_review_required']=True
            other['criteria']={x['id']:{'status':'unknown','reason':'Brief changed; reassess this criterion.','source_ids':[]} for x in b['criteria']}
    s.update(brief=b,sources=source_list,selected=c['id'],view='location',comparison=[],stage='location');s.pop('camera_override',None)
    new_history(s,'replace',{'removed':id,'added':c['id'],'brief_changed':brief is not None});return s

def reassess(s,id,payload):
    need(not s.get('ended'),'Session ended');s=copy.deepcopy(s);c=candidate(s,id)
    need(isinstance(payload,dict) and set(payload)<= {'creative_fit','tradeoffs','criteria','checks'},'Reassessment can update fit, tradeoffs, criteria and checks only')
    c.update(payload);validate_candidate(c,s['brief'],{x['id'] for x in s['sources']});c.pop('fit_review_required',None)
    new_history(s,'reassess',{'id':id});return s

def view_values(s):
    if s['view']=='location':
        c=candidate(s);v={'target':c['coordinates'],'range':350,'tilt':75,'heading':0};v.update(c.get('camera',{}))
        # Close by default even for older plans authored with a broad camera.
        # Explicit live camera adjustments can still widen the view.
        v['range']=min(v['range'],350);v['tilt']=max(v['tilt'],75)
        v.update(s.get('camera_override',{}));return v
    points=[c['coordinates'] for c in s['candidates'] if s['view']!='compare' or c['id'] in s['comparison']]
    # Spherical mean avoids putting dateline-crossing shortlists at Greenwich.
    vs=[(math.cos(math.radians(p[1]))*math.cos(math.radians(p[0])),math.cos(math.radians(p[1]))*math.sin(math.radians(p[0])),math.sin(math.radians(p[1]))) for p in points]
    x,y,z=[sum(v[i] for v in vs)/len(vs) for i in range(3)];target=[math.degrees(math.atan2(y,x)),math.degrees(math.atan2(z,math.hypot(x,y)))]
    return {'target':target,'range':max(5000,max(distance(target,p) for p in points)*3300),'tilt':25,'heading':0}

def camera_xml(s):
    v=view_values(s);root=ET.Element('LookAt')
    for k,value in [('longitude',v['target'][0]),('latitude',v['target'][1]),('altitude',0),('heading',v['heading']),('tilt',v['tilt']),('range',v['range']),('altitudeMode','relativeToGround')]:ET.SubElement(root,k).text=str(value)
    return ET.tostring(root,encoding='unicode')

def camera_change(s,range=None,tilt=None,heading=None):
    need(not s.get('ended') and s['view']=='location','Open a candidate before adjusting its view')
    s=copy.deepcopy(s);v=s.setdefault('camera_override',{})
    for k,value,lo,hi in [('range',range,50,3500),('tilt',tilt,50,78),('heading',heading,0,360)]:
        if value is not None:v[k]=number(value,k,lo,hi)
    return s

def color(hex):return 'ff'+hex[5:7]+hex[3:5]+hex[1:3]

def geometry(s):
    root,doc=rig.document();rig.tag(doc,'name','SceneScout candidates; markers are not access boundaries')
    for i,c in enumerate(s['candidates']):
        if s['view']=='location' and c['id']!=s['selected']:continue
        if s['view']=='compare' and c['id'] not in s['comparison']:continue
        lon,lat=c['coordinates'];p=rig.tag(doc,'Placemark');rig.tag(p,'name',chr(65+i)+' / '+c['name'])
        st=rig.tag(p,'Style');ic=rig.tag(st,'IconStyle');rig.tag(ic,'scale',1.05);rig.tag(rig.tag(ic,'Icon'),'href',rig.URL+'/pin-'+str(i)+'.png')
        rig.tag(ic,'hotSpot',x='0.5',y='0',xunits='fraction',yunits='fraction');ls=rig.tag(st,'LabelStyle');rig.tag(ls,'scale',.75);rig.tag(ls,'color','fff7f3ed')
        pt=rig.tag(p,'Point');rig.tag(pt,'altitudeMode','clampToGround');rig.tag(pt,'coordinates',str(lon)+','+str(lat)+',0')
        points=[]
        for n in range(65):
            a=2*math.pi*n/64;points.append((lon+.045*math.cos(a)/(111*math.cos(math.radians(lat))),lat+.045*math.sin(a)/111,0))
        rig.line(doc,points,color(PALETTE[i]),2.5)
    return rig.xml(root)

def reply(s):
    if s['view']=='overview':return 'Three researched scouting candidates are on the globe. '+s['brief']['summary']+' Say show A, B or C, compare candidates, or save a candidate. The radius is straight-line distance, not driving distance.'
    if s['view']=='compare':return 'Comparing '+', '.join(candidate(s,x)['name'] for x in s['comparison'])+'. Fit is a creative judgment. Documented evidence and unresolved checks are separate. Choose a candidate to inspect or save.'
    c=candidate(s);i=s['candidates'].index(c)
    return chr(65+i)+': '+c['name']+'. '+c['creative_fit']+' Trade-off: '+c['tradeoffs']+' Next check: '+c['checks'][0].rstrip('. ')+'. Say save this, show next, compare, or change the brief.'

def render(s,dest):
    import scout_visuals as visual
    dest=Path(dest);dest.mkdir(parents=True,exist_ok=True)
    (dest/'scene.kml').write_bytes(geometry(s));(dest/'camera.xml').write_text(camera_xml(s));(dest/'live.kml').write_bytes(rig.networklink())
    visual.panel(s,dest/'panel.png');visual.branding(s,dest/'branding.png');visual.pins(dest)
    (dest/'reply.txt').write_text(reply(s));return dest

def publish(s):
    # Persist the intended operation before the first remote mutation. Continue retries it.
    with tempfile.TemporaryDirectory(prefix='scene-scout-') as tmp:
        p=render(s,Path(tmp));s['pending_display']=True;save(s)
        d=rig.connection();r=rig.Rig(d);r.ssh('mkdir -p '+rig.shlex.quote(rig.REMOTE));r.copy([p/('pin-'+str(i)+'.png') for i in range(3)])
        rig.deploy(s,scene_data=(p/'scene.kml').read_bytes(),panel_path=p/'panel.png',camera_xml=(p/'camera.xml').read_text(),branding_path=p/'branding.png')
    s.pop('pending_display',None);save(s);message=reply(s)
    print('SCOUTING REPLY:\n'+message+'\nUse the Nara chat to respond. Visually confirm the rig display.')
    if s.get('voice'):
        from local_voice import narrate
        narrate(message)

def import_photos(s):
    from PIL import Image,ImageOps
    s=copy.deepcopy(s)
    for c in s['candidates']:
        if 'photo' not in c:continue
        src=Path(c['photo']['path']).expanduser();need(src.is_file() and src.stat().st_size<=12_000_000,'Local source photo missing or larger than 12 MB')
        dest=rig.HOME/'state/scene-scout-media'/s['session_id'];dest.mkdir(parents=True,exist_ok=True)
        with Image.open(src) as im:
            need(im.width*im.height<=24_000_000,'Photo pixel dimensions too large');im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((1600,1000));target=dest/(c['id']+'.jpg');im.save(target,quality=88)
        os.chmod(target,0o600);c['photo']['path']=str(target.resolve())
    return s

def linked_report(report):
    parts=[];last=0
    for match in re.finditer(r'https://[^\s<>\"\']+',report):
        parts.append(html.escape(report[last:match.start()]))
        url=html.escape(match.group(),quote=True);parts.append('<a style="color:#75ddd1" href="'+url+'">'+url+'</a>');last=match.end()
    parts.append(html.escape(report[last:]));return ''.join(parts)

def export(s,output):
    dest=Path(output).expanduser().resolve();dest.mkdir(parents=True,exist_ok=True)
    lines=['# SceneScout scouting report','',s['brief']['title'],'',s['brief']['summary'],'','Search area: '+s['brief']['city']+'; '+str(s['brief']['radius_km'])+' km straight-line radius.','',
           'This is a research shortlist, not a site inspection, access permit or confirmed shoot booking.','', '## Creative brief','']
    for x in s['brief']['criteria']:lines.append('- '+x['priority'].upper()+': '+x['label'])
    for i,c in enumerate(s['candidates']):
        d=s['decisions'][c['id']];lon,lat=c['coordinates'];lines+=['','## '+chr(65+i)+' / '+c['name'],'','Decision: '+d['status'],'','Note: '+(d['note'] or 'None'),'','Coordinates: '+str(lat)+', '+str(lon)+' ('+c['coordinate_precision']+' reference; verify exact shooting position).','',
            'Map: https://www.google.com/maps/search/?api=1&query='+str(lat)+','+str(lon),'','### Creative assessment','',c['creative_fit'],'','Trade-offs: '+c['tradeoffs']]
        if c.get('fit_review_required'):lines+=['','BRIEF CHANGED: this retained candidate needs reassessment.']
        lines+=['','### Documented facts','']
        for f in c['facts']:lines.append('- '+f['text']+' ['+', '.join(f['source_ids'])+']')
        lines+=['','### Criteria','']
        for criterion in s['brief']['criteria']:
            v=c['criteria'][criterion['id']];lines.append('- '+criterion['label']+': '+v['status']+'; '+v['reason'])
        lines+=['','### Practical evidence','']
        for k,v in c['practical'].items():lines.append('- '+k+': '+v['status']+'; '+v['text']+' ['+', '.join(v['source_ids'])+']')
        lines+=['','### On-site checks','']+['- '+x for x in c['checks']]
        if 'photo' in c:lines+=['','Photo credit: '+c['photo']['credit']+'; '+c['photo']['usage']]
    lines+=['','## Sources','']
    for x in s['sources']:lines+=['- '+x['id']+': '+x['title']+' — '+x['url']+' (accessed '+x['accessed']+'). '+x['supports']]
    lines+=['','## Session history','']+[json.dumps(x,ensure_ascii=False) for x in s['history']]
    report='\n'.join(lines)+'\n';(dest/'scouting-report.md').write_text(report,encoding='utf-8')
    (dest/'scouting-report.html').write_text('<!doctype html><meta charset="utf-8"><title>SceneScout scouting report</title><style>body{background:#101820;color:#eef1f4;max-width:1000px;margin:50px auto;padding:24px;font:17px/1.6 system-ui}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}</style><h1>SceneScout</h1><pre>'+linked_report(report)+'</pre>',encoding='utf-8')
    geo={'type':'FeatureCollection','features':[{'type':'Feature','geometry':{'type':'Point','coordinates':c['coordinates']},'properties':{'id':c['id'],'name':c['name'],'decision':s['decisions'][c['id']]['status'],'coordinate_precision':c['coordinate_precision'],'fit_review_required':c.get('fit_review_required',False)}} for c in s['candidates']]}
    (dest/'shortlist.geojson').write_text(json.dumps(geo,indent=2),encoding='utf-8')
    print('Exported report and GeoJSON to '+str(dest));return dest

def context(s):
    result={k:s[k] for k in ('session_id','brief','selected','view','voice','decisions','candidates','sources','ended')}
    result['pending_display']=s.get('pending_display',False);return result

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action',choices=['check','diagnose','validate','render','start','context','status','show','next','overview','compare','mark','replace','reassess','camera','continue','speak','export','end'])
    ap.add_argument('--plan',type=Path);ap.add_argument('--output',type=Path);ap.add_argument('--id');ap.add_argument('--ids',nargs='+');ap.add_argument('--decision',choices=DECISIONS);ap.add_argument('--note',default='')
    ap.add_argument('--candidate-json',type=Path);ap.add_argument('--brief-json',type=Path);ap.add_argument('--assessment-json',type=Path);ap.add_argument('--allow-saved',action='store_true');ap.add_argument('--voice',action='store_true');ap.add_argument('--silent',action='store_true')
    ap.add_argument('--range',type=float);ap.add_argument('--tilt',type=float);ap.add_argument('--heading',type=float)
    a=ap.parse_args()
    if a.action=='diagnose':
        from scout_diagnostics import diagnose
        diagnose();return
    if a.action=='check':
        from PIL import Image
        import scout_visuals as v
        v.font(30);d=rig.connection();print('Ready: Pillow, bundled fonts and machine-verified saved connection; '+str(d['screens'])+' screens. No SSH connection attempted.');return
    if a.action in ('validate','render','start'):
        need(a.plan is not None,'--plan is required');plan=validate(load_json(a.plan))
        if a.action=='validate':print('Structure valid: 3 candidates. Absolute plan: '+str(a.plan.resolve())+'\nSources and permissions still require factual verification.');return
        s=initial(plan,a.voice)
        if a.action=='render':need(a.output is not None,'--output required');render(s,a.output);print('Rendered locally: '+str(a.output.resolve()));return
        if STATE.exists():need(read().get('ended',False) or read().get('restored',False),'A session is active. End scouting before starting a new one.')
        # Do not stack side-panel backups over an active classroom session.
        for n in ('globe-classroom-live.json','globe-classroom.json'):
            p=rig.HOME/'state'/n
            if p.exists():
                other=json.loads(p.read_text());need(not other.get('backup') or other.get('restored'), 'End the active Globe Classroom lesson before starting SceneScout.')
                break
        s=import_photos(s);publish(s);return
    s=read()
    # Resolve user-visible A/B/C to stable IDs at the moment of execution.
    if a.id and a.id.upper() in ('A','B','C'):a.id=s['candidates'][ord(a.id.upper())-65]['id']
    if a.ids:a.ids=[s['candidates'][ord(x.upper())-65]['id'] if x.upper() in ('A','B','C') else x for x in a.ids]
    if a.action in ('context','status'):print(json.dumps(context(s),indent=2,ensure_ascii=False));return
    if a.action=='export':need(a.output is not None,'--output required');export(s,a.output);return
    if a.action=='end':
        if s.get('backup'):rig.restore(s)
        s['ended']=True;new_history(s,'end',{});save(s);print('Scouting ended. Decisions and exports are retained. Confirm markers and panels disappeared.');return
    need(not s.get('ended') and not s.get('restored'),'Session ended. Start a new plan; exporting is still available.')
    if a.action=='speak':
        from local_voice import narrate
        narrate(reply(s));return
    if a.action=='replace':
        need(a.id and a.candidate_json,'replace requires --id and --candidate-json');s=replace(s,a.id,load_json(a.candidate_json),load_json(a.brief_json) if a.brief_json else None,a.allow_saved);s=import_photos(s)
    elif a.action=='reassess':need(a.id and a.assessment_json,'reassess requires --id and --assessment-json');s=reassess(s,a.id,load_json(a.assessment_json))
    elif a.action=='camera':s=camera_change(s,a.range,a.tilt,a.heading)
    elif a.action in ('show','next','overview','compare','mark'):
        if a.action in ('show','mark'):need(a.id,'--id required')
        s=change(s,a.action,a.id,a.decision,a.note,a.ids)
    if a.voice:s['voice']=True
    if a.silent:s['voice']=False
    publish(s)

if __name__=='__main__':
    try:
        import fcntl
        STATE.parent.mkdir(parents=True,exist_ok=True)
        with (STATE.parent/'scene-scout.lock').open('a') as lock:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise RuntimeError('Another SceneScout operation is running. Wait for it to finish.')
            main()
    except (ValueError,RuntimeError,OSError,KeyError,TypeError,subprocess.TimeoutExpired) as exc:
        print('SceneScout: '+str(exc),file=sys.stderr);sys.exit(1)
