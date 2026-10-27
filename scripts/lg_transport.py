#!/usr/bin/env python3
"""SceneScout transport adapted from tested SceneScout transport (Apache-2.0).
Remote cleanup intentionally supports the rig's Python 3.5.
"""
import hashlib,json,math,os,shlex,shutil,subprocess,tempfile,time
from pathlib import Path
import xml.etree.ElementTree as ET
K='http://www.opengis.net/kml/2.2'
ET.register_namespace('',K)
ROOT=Path(__file__).resolve().parents[1]
HOME=Path(os.environ.get('HERMES_HOME',Path.home()/'.hermes/profiles/liquid-galaxy-agent')).expanduser()
STATE=HOME/'state/scene-scout.json'
REMOTE='/var/www/html/kml/scene-scout'
URL='http://lg1:81/kml/scene-scout'
def save_state(s):
    STATE.parent.mkdir(parents=True,exist_ok=True)
    p=STATE.with_suffix('.tmp');p.write_text(json.dumps(s,indent=2)+'\n');os.chmod(p,0o600);p.replace(STATE)
def tag(parent, name, text=None, **attrs):
    e = ET.SubElement(parent, '{%s}%s' % (K,name), attrs)
    if text is not None:
        e.text = str(text)
    return e

def document():
    root = ET.Element('{%s}kml' % K)
    return root, tag(root,'Document')

def xml(root):
    data = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    ET.fromstring(data)
    return data

def line(doc, points, color, width=7, mode='clampToGround'):
    p = tag(doc,'Placemark')
    style = tag(p,'Style')
    ls = tag(style,'LineStyle')
    tag(ls,'color',color); tag(ls,'width',width)
    geom = tag(p,'LineString')
    tag(geom,'altitudeMode',mode)
    if mode == 'clampToGround': tag(geom,'tessellate',1)
    tag(geom,'coordinates',' '.join('%s,%s,%s' % xyz for xyz in points))

def overlay(image_url):
    root,doc=document()
    o=tag(doc,'ScreenOverlay'); tag(o,'name','SceneScout panel'); tag(o,'drawOrder',1000)
    tag(tag(o,'Icon'),'href',image_url)
    tag(o,'overlayXY',x='0.5',y='0.5',xunits='fraction',yunits='fraction')
    tag(o,'screenXY',x='0.5',y='0.5',xunits='fraction',yunits='fraction')
    # Zero height preserves the image aspect ratio; avoids stretching in VM windows.
    tag(o,'size',x='0.90',y='0',xunits='fraction',yunits='fraction')
    return xml(root)

def networklink():
    root,doc=document(); n=tag(doc,'NetworkLink')
    tag(n,'name','SceneScout: automatic scene updates')
    link=tag(n,'Link'); tag(link,'href',URL+'/scene.kml')
    tag(link,'refreshMode','onInterval'); tag(link,'refreshInterval',2)
    return xml(root)

def connection():
    path=HOME/'state/lg-connection.json'
    if not path.exists(): raise RuntimeError('Nara connection profile is missing. Complete LG onboarding first.')
    d=json.loads(path.read_text())
    machine=''
    for p in ['/etc/machine-id','/var/lib/dbus/machine-id']:
        if Path(p).exists() and Path(p).read_text().strip():
            machine=Path(p).read_text().strip(); break
    import socket
    fp=hashlib.sha256('|'.join([machine,socket.gethostname(),str(Path.home().resolve())]).encode()).hexdigest()
    if not d.get('verified') or d.get('machine_fingerprint')!=fp:
        raise RuntimeError('Connection profile is not verified for this computer. Run Nara onboarding.')
    if not isinstance(d.get('screens'),int) or d['screens']<3 or d['screens']%2==0:
        raise RuntimeError('This version supports the standard odd LG layout with 3, 5, 7... screens.')
    if not shutil.which('sshpass'): raise RuntimeError('sshpass is missing. Install it in Ubuntu WSL.')
    return d

class Rig:
    def __init__(self,d):
        self.d=d
        self.env=dict(os.environ,SSHPASS=d['password'])
        self.options=['-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=10']
        self.target='%s@%s'%(d['username'],d['ip'])
    def ssh(self,command,data=None):
        cmd=['sshpass','-e','ssh',*self.options,'-p',str(self.d['port']),self.target,command]
        p=subprocess.run(cmd,input=data,capture_output=True,env=self.env,timeout=30)
        if p.returncode:
            detail=p.stderr.decode(errors='replace').replace(self.d['password'],'[redacted]')
            raise RuntimeError('SSH failed: '+detail[-1500:])
        return p.stdout.decode().strip()
    def copy(self,paths):
        cmd=['sshpass','-e','scp','-O',*self.options,'-P',str(self.d['port']),*[str(p) for p in paths],self.target+':'+REMOTE+'/']
        p=subprocess.run(cmd,capture_output=True,env=self.env,timeout=45)
        if p.returncode:
            detail=p.stderr.decode(errors='replace').replace(self.d['password'],'[redacted]')
            raise RuntimeError('SCP failed: '+detail[-1500:])

def prepare_backup(rig,s):
    if s.get('backup'): return
    # Persist the backup location before mutation so an interrupted deploy is recoverable.
    backup='/home/%s/scene-scout-backup-%s'%(rig.d['username'],time.time_ns())
    # The account home is discovered, rather than assumed from username.
    remote_home=rig.ssh('printf "%s" "$HOME"')
    backup=remote_home+'/scene-scout-backup-'+str(time.time_ns())
    right=rig.d['screens']//2+1; left=right+1
    files=['/var/www/html/kmls.txt','/var/www/html/kml/slave_%s.kml'%right,'/var/www/html/kml/slave_%s.kml'%left]
    cmds=['set -eu','mkdir -p '+shlex.quote(backup)]
    for i,f in enumerate(files):
        cmds.append('if [ -f {f} ]; then cp -p {f} {b}/{i}; else touch {b}/{i}.absent; fi'.format(f=shlex.quote(f),b=shlex.quote(backup),i=i))
    rig.ssh('\n'.join(cmds))
    s.update(backup=backup,backup_files=files)
    save_state(s)

def deploy(s, scene_data=None, panel_path=None, camera_xml=None, branding_path=None):
    d=connection(); rig=Rig(d)
    host=rig.ssh('hostname')
    if not host: raise RuntimeError('SSH verification returned an empty hostname.')
    prepare_backup(rig,s)
    rig.ssh('mkdir -p '+shlex.quote(REMOTE))
    stage=s['stage']; token=str(time.time_ns())
    if scene_data is None or panel_path is None or camera_xml is None or branding_path is None:
        raise ValueError('A complete rendered scene is required')
    with tempfile.TemporaryDirectory(prefix='scene-scout-') as temp:
        p=Path(temp)
        (p/'live.kml').write_bytes(networklink())
        (p/'scene-next.kml').write_bytes(scene_data)
        shutil.copyfile(panel_path,p/('panel-%s.png'%token))
        shutil.copyfile(branding_path,p/('branding-%s.png'%token))
        right=d['screens']//2+1; left=right+1
        (p/('slave_%s.kml'%right)).write_bytes(overlay(URL+'/panel-%s.png'%token))
        (p/('slave_%s.kml'%left)).write_bytes(overlay(URL+'/branding-%s.png'%token))
        rig.copy(list(p.iterdir()))
    # Preserve other applications' links. Bootstrap once; scenes refresh through live.kml.
    link=URL+'/live.kml'
    cmd='set -eu\n'
    cmd+='mv '+REMOTE+'/scene-next.kml '+REMOTE+'/scene.kml\n'
    cmd+='touch /var/www/html/kmls.txt\n'
    cmd+='grep -Fqx {u} /var/www/html/kmls.txt || printf "\\n%s\\n" {u} >> /var/www/html/kmls.txt\n'.format(u=shlex.quote(link))
    for n in [right,left]:
        cmd+='cp {r}/slave_{n}.kml /var/www/html/kml/slave_{n}.kml\n'.format(r=REMOTE,n=n)
    cmd+='printf "%s\\n" '+shlex.quote('flytoview='+(camera_xml))+' > /tmp/query.txt\n'
    rig.ssh(cmd)
    s['deployed_at']=time.time(); save_state(s)
    print('Deployed stage %s to %s; right panel lg%s, left branding lg%s.'%(stage,host,right,left))
    print('Check the rig visually. File transfer success does not prove Earth rendered the scene.')

def restore(s):
    if not s.get('backup'): raise RuntimeError('There is no display backup for this scouting session.')
    rig=Rig(connection())
    # Serve an empty scene FIRST: removing a loading-list URL alone can leave
    # geometry in a cached, still-loaded NetworkLink in Google Earth.
    rig.ssh('mkdir -p '+shlex.quote(REMOTE))
    with tempfile.TemporaryDirectory(prefix='scout-cleanup-') as folder:
        p=Path(folder)/'scene-empty.kml'; p.write_bytes(xml(document()[0])); rig.copy([p])
    rig.ssh('mv '+shlex.quote(REMOTE+'/scene-empty.kml')+' '+shlex.quote(REMOTE+'/scene.kml')+'; sleep 3')
    # Preserve links added by other applications after the lesson began.
    # Restore a shared side file only while it still belongs to this skill.
    script="""from pathlib import Path
import json
backup=Path(BACKUP)
files=FILES
prefix=PREFIX
empty=EMPTY
loading=Path('/var/www/html/kmls.txt')
if loading.exists():
    lines=[v for v in loading.read_text().splitlines() if v.strip() and not v.strip().startswith(prefix)]
    loading.write_text('\\n'.join(lines)+('\\n' if lines else ''))
for i,name in enumerate(files):
    if i==0: continue
    target=Path(name)
    if not target.exists() or prefix not in target.read_text(errors='replace'): continue
    if (backup/(str(i)+'.absent')).exists(): target.write_bytes(empty)
    else: target.write_bytes((backup/str(i)).read_bytes())
"""
    script=script.replace('BACKUP',repr(s['backup'])).replace('FILES',repr(s['backup_files'])).replace('PREFIX',repr(URL+'/')).replace('EMPTY',repr(xml(document()[0])))
    rig.ssh('python3 -',data=script.encode('utf-8'))
    s['restored']=True; s['ended_at']=time.time(); save_state(s)
    print('Ended scouting: served an empty scene before removing SceneScout loading links.')
    print('Restored SceneScout-owned side overlays; retained other applications’ current content, scouting records and backups.')
    print('Camera position unchanged. Confirm markers and SceneScout panels disappeared on the rig; HTTP/file success is not visual proof.')
