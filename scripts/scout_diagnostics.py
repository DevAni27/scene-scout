"""Read-only LG checks. Does not change myplaces, routing, imagery or credentials."""
import json
import lg_transport as t

REMOTE_CHECK = r'''
import json,os,struct,subprocess
from pathlib import Path
import urllib.request
import xml.etree.ElementTree as ET
root=Path('/var/www/html/kml')
ns={'k':'http://www.opengis.net/kml/2.2'}
result={}
for name,n in [('right',RIGHT),('left',LEFT)]:
    p=root/('slave_'+str(n)+'.kml')
    row={'screen':'lg'+str(n),'file_exists':p.exists()}
    if p.exists():
        try:
            tree=ET.fromstring(p.read_bytes())
            urls=[x.text for x in tree.findall('.//k:ScreenOverlay/k:Icon/k:href',ns)]
            owned=[x for x in urls if x and x.startswith('http://lg1:81/kml/scene-scout/')]
            row['scout_overlay_urls']=owned
            if owned:
                try:
                    with urllib.request.urlopen(owned[0],timeout=5) as response:
                        header=response.read(24)
                        row['http_status']=response.getcode()
                        if header[:8]==b'\x89PNG\r\n\x1a\n':row['png_size']=list(struct.unpack('>II',header[16:24]))
                except Exception as exc:row['image_fetch_error']=str(exc)[:220]
        except Exception as exc:row['parse_error']=str(exc)[:220]
    result[name]=row
client_code="""from pathlib import Path
import json
import xml.etree.ElementTree as ET
ns={'k':'http://www.opengis.net/kml/2.2'}
p=Path.home()/'.googleearth/myplaces.kml'
out={'runtime_file_exists':p.exists(),'side_network_links':[]}
if p.exists():
    try:
        tree=ET.fromstring(p.read_bytes())
        for link in tree.findall('.//k:NetworkLink',ns):
            href=link.findtext('k:Link/k:href',default='',namespaces=ns)
            if '/slave_' in href:
                out['side_network_links'].append({'href':href,'refreshMode':link.findtext('k:Link/k:refreshMode',default='',namespaces=ns),'refreshInterval':link.findtext('k:Link/k:refreshInterval',default='',namespaces=ns)})
    except Exception as exc:out['parse_error']=str(exc)[:180]
print(json.dumps(out))
"""
try:
    p=subprocess.Popen(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=5','lg'+str(LEFT),'python3 -'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    stdout,stderr=p.communicate(client_code.encode('utf-8'),timeout=9)
    if p.returncode==0:result['left_client']=json.loads(stdout.decode('utf-8'))
    else:result['left_client']={'error':'Could not inspect lg'+str(LEFT)+' with the master existing SSH trust; no configuration changed.'}
except Exception as exc:
    try:p.kill()
    except Exception:pass
    result['left_client']={'error':str(exc)[:180]}
print(json.dumps(result,indent=2))
'''

def diagnose():
    d=t.connection();script=REMOTE_CHECK.replace('RIGHT',str(d['screens']//2+1)).replace('LEFT',str(d['screens']//2+2))
    print(t.Rig(d).ssh('python3 -',data=script.encode('utf-8')))
    print('Read-only check. A missing/failed image or side NetworkLink is separate from Gemini quota and Earth tile quality.')
