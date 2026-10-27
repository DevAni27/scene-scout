"""SceneScout's shared visual system. All text uses bundled fonts, no browser/CSS dependency."""
from pathlib import Path
from functools import lru_cache
import math
from PIL import Image,ImageDraw,ImageFont,ImageOps
import scout_engine as e

BG='#0c141d';CARD='#14222e';EDGE='#2c3c49';WHITE='#f2f4ef';MUTED='#aebcc3';FAINT='#7f939e';ACCENT='#75ddd1';GOLD='#edbc7a'

@lru_cache(maxsize=64)
def font(size,bold=False):return ImageFont.truetype(str(e.ROOT/'assets'/('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')),size)

def wrap(d,text,size,width,bold=False):
    lines=[]
    for paragraph in str(text).split('\n'):
        line=''
        for word in paragraph.split():
            # Source URLs can be long; only metadata uses ellipsis, body must fit.
            if d.textlength(word,font=font(size,bold))>width:raise ValueError('Panel has an unbroken word too long to render; shorten it')
            proposed=(line+' '+word).strip()
            if line and d.textlength(proposed,font=font(size,bold))>width:lines.append(line);line=word
            else:line=proposed
        if line:lines.append(line)
    return lines

def block(d,text,box,size=32,minimum=23,color=WHITE,bold=False,gap=8):
    x,y,w,h=box
    for s in range(size,minimum-1,-1):
        try:rows=wrap(d,text,s,w,bold)
        except ValueError:continue
        if len(rows)*(s+gap)<=h:
            for row in rows:d.text((x,y),row,font=font(s,bold),fill=color);y+=s+gap
            return y
    raise ValueError('Panel content does not fit: shorten the field before deployment')

def ellipsis(d,text,width,size=20):
    if d.textlength(text,font=font(size))<=width:return text
    while text and d.textlength(text+'…',font=font(size))>width:text=text[:-1]
    return text+'…'

def base(s,label):
    im=Image.new('RGB',(1920,1080),BG);d=ImageDraw.Draw(im)
    d.text((82,38),'SCENESCOUT',font=font(27,True),fill=WHITE)
    d.text((82,78),'A LOCATION IS A CREATIVE CHOICE',font=font(16),fill=FAINT)
    d.text((1370,43),label,font=font(23,True),fill=ACCENT)
    d.line((82,118,1838,118),fill=EDGE,width=2)
    d.text((82,1010),'RESEARCHED SHORTLIST  /  VERIFY ON SITE',font=font(17,True),fill=FAINT)
    d.text((1320,1010),'LIQUID GALAXY  /  NARA',font=font(18),fill=MUTED)
    return im,d

def card(d,box):d.rounded_rectangle(box,radius=18,fill=CARD,outline=EDGE,width=1)

def action(d,message):
    card(d,(82,898,1838,982));d.rectangle((82,913,87,965),fill=ACCENT)
    d.text((108,911),'IN NARA CHAT',font=font(16,True),fill=ACCENT)
    block(d,message,(108,937,1690,35),size=24,minimum=20,gap=4)

def source_footer(d,s,c,y=858):
    used=list(dict.fromkeys([c['coordinate_source_id']]+[x for f in c['facts'] for x in f['source_ids']]))
    titles={x['id']:x for x in s['sources']}
    label='SOURCES  '+ '  /  '.join(titles[x]['title'] for x in used[:3])
    d.text((84,y),ellipsis(d,label,1740,18),font=font(18),fill=FAINT)

def photo(im,d,c,box):
    x,y,w,h=box;p=c.get('photo')
    if not p:return False
    with Image.open(p['path']) as src:
        src=ImageOps.exif_transpose(src).convert('RGB');src=ImageOps.contain(src,(w,h-40));im.paste(src,(x+(w-src.width)//2,y+(h-40-src.height)//2))
    d.text((x,y+h-30),ellipsis(d,p['credit'],w,16),font=font(16),fill=MUTED)
    return True

def panel(s,path):
    label={'overview':'SHORTLIST / 03','compare':'COMPARE','location':'LOCATION STUDY'}[s['view']]
    im,d=base(s,label)
    if s['view']=='location':
        c=e.candidate(s);i=s['candidates'].index(c);decision=s['decisions'][c['id']]['status'].upper()
        block(d,chr(65+i)+' / '+c['name'],(82,153,1756,118),size=53,minimum=36,bold=True)
        dist=e.distance(s['brief']['origin'],c['coordinates'])
        d.text((85,280),decision+'   ·   '+('AREA REFERENCE' if c['coordinate_precision']=='area' else 'SITE REFERENCE')+'   ·   %.1f KM STRAIGHT-LINE'%dist,font=font(20),fill=e.PALETTE[i])
        if c.get('fit_review_required'):d.text((85,315),'BRIEF CHANGED — FIT NEEDS REASSESSMENT',font=font(20,True),fill=GOLD)
        d.text((85,355),'CREATIVE FIT  /  INTERPRETATION',font=font(18,True),fill=ACCENT)
        block(d,c['creative_fit'],(85,392,1000,164),size=33,minimum=25)
        d.text((85,574),'TRADE-OFF',font=font(17,True),fill=GOLD)
        block(d,c['tradeoffs'],(85,609,1000,104),size=27,minimum=22,gap=6)
        card(d,(1130,347,1838,713))
        if not photo(im,d,c,(1154,366,660,320)):
            d.text((1154,370),'DOCUMENTED EVIDENCE',font=font(18,True),fill=MUTED)
            evidence='\n'.join('• '+f['text'] for f in c['facts'][:2])
            block(d,evidence,(1154,410,660,244),size=27,minimum=22,gap=9)
            d.text((1154,676),'NO SOURCE PHOTO ATTACHED',font=font(16),fill=FAINT)
        for j,k in enumerate(('access','facilities','permission')):
            x=82+j*590;v=c['practical'][k];card(d,(x,720,x+576,841))
            d.text((x+18,733),k.upper()+' / '+v['status'].upper(),font=font(17,True),fill=ACCENT if v['status']=='documented' else GOLD)
            block(d,v['text'],(x+18,764,540,68),size=21,minimum=17,gap=4)
        source_footer(d,s,c)
        action(d,'Save '+chr(65+i)+'  ·  Next location  ·  Compare  ·  Closer / wider view  ·  Replace this candidate')
    elif s['view']=='overview':
        block(d,s['brief']['title'],(82,153,1756,115),size=52,minimum=36,bold=True)
        block(d,s['brief']['summary'],(85,285,1740,100),size=30,minimum=25)
        for i,c in enumerate(s['candidates']):
            x=82+i*590;card(d,(x,421,x+576,841))
            d.text((x+24,445),chr(65+i)+'   /   '+s['decisions'][c['id']]['status'].upper(),font=font(22,True),fill=e.PALETTE[i])
            block(d,c['name'],(x+24,491,525,96),size=32,minimum=25,bold=True)
            block(d,c['creative_fit'],(x+24,600,525,180),size=26,minimum=20,gap=7)
            if c.get('fit_review_required'):d.text((x+24,807),'FIT NEEDS REVIEW',font=font(17,True),fill=GOLD)
            else:d.text((x+24,807),'%.1f KM / STRAIGHT-LINE'%e.distance(s['brief']['origin'],c['coordinates']),font=font(17),fill=FAINT)
        d.text((85,850),'Markers indicate candidate areas, not verified entry points, boundaries or routes.',font=font(21),fill=MUTED)
        action(d,'Show A, B or C  ·  Compare candidates  ·  Save a location  ·  Refine the brief')
    else:
        selected=[e.candidate(s,x) for x in s['comparison']];n=len(selected);width=(1756-24*(n-1))/n
        block(d,'A different place. A different compromise.',(82,152,1756,90),size=48,minimum=34,bold=True)
        d.text((85,265),'Qualitative assessment against your brief. No invented fit score.',font=font(25),fill=MUTED)
        for j,c in enumerate(selected):
            i=s['candidates'].index(c);x=int(82+j*(width+24));w=int(width);card(d,(x,334,x+w,858))
            d.text((x+22,355),chr(65+i)+' / '+s['decisions'][c['id']]['status'].upper(),font=font(20,True),fill=e.PALETTE[i])
            block(d,c['name'],(x+22,401,w-44,92),size=31,minimum=24,bold=True)
            crit=s['brief']['criteria'];spacing=min(110,330/len(crit))
            for k,item in enumerate(crit):
                v=c['criteria'][item['id']];y=515+k*spacing
                name=ellipsis(d,item['label'],w-44,20)
                d.text((x+22,y),name,font=font(20),fill=MUTED)
                d.text((x+22,y+27),('REASSESS' if c.get('fit_review_required') else v['status'].upper()),font=font(18,True),fill=GOLD if v['status'] in ('unknown','conflicts','partial') else ACCENT)
                if len(crit)<=3:d.text((x+22,y+58),ellipsis(d,v['reason'],w-44,18),font=font(18),fill=FAINT)
        action(d,'Show a candidate  ·  Save or reject  ·  Change a requirement  ·  Export scouting report')
    im.save(path)

def branding(s,path):
    im=Image.new('RGB',(1920,1080),BG);d=ImageDraw.Draw(im)
    d.text((110,65),'LIQUID GALAXY  /  NARA',font=font(22),fill=MUTED)
    # Lens/compass emblem: deliberately restrained, not a map/photo substitute.
    cx,cy=960,290
    for r in (86,116,138):d.ellipse((cx-r,cy-r,cx+r,cy+r),outline=ACCENT if r==116 else EDGE,width=3)
    for x,y in ((-165,0),(165,0),(0,-165),(0,165)):
        d.line((cx+x*.85,cy+y*.85,cx+x,cy+y),fill=MUTED,width=3)
    d.text((960,480),'SCENESCOUT',anchor='mt',font=font(84,True),fill=WHITE)
    d.text((960,589),'FIND THE PLACE. KEEP THE VISION.',anchor='mt',font=font(26),fill=ACCENT)
    d.line((190,675,1730,675),fill=EDGE,width=2)
    block(d,s['brief']['title'],(190,720,1540,100),size=41,minimum=30,bold=True)
    block(d,s['brief']['city']+'  /  '+str(s['brief']['radius_km'])+' KM SEARCH RADIUS',(190,845,1540,60),size=25,minimum=22,color=MUTED)
    count=sum(x['status']=='saved' for x in s['decisions'].values())
    d.text((190,946),'03 CANDIDATES   /   %02d SAVED'%count,font=font(23,True),fill=ACCENT)
    im.save(path)

def pins(dest):
    for i,color in enumerate(e.PALETTE):
        im=Image.new('RGBA',(96,120),(0,0,0,0));d=ImageDraw.Draw(im)
        d.polygon([(26,65),(70,65),(48,115)],fill=BG)
        d.ellipse((10,8,86,84),fill=BG,outline=color,width=4)
        d.text((48,42),chr(65+i),anchor='mm',font=font(43,True),fill=color)
        im.save(Path(dest)/('pin-'+str(i)+'.png'))
