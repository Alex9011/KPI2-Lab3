#!/usr/bin/env python3
"""Deterministic offline SVG/PNG renderer for this project's Mermaid sequence subset.

Parses participant/actor, message and return, activate/deactivate, alt/else,
opt, loop, par/and, Note over and end. Exits on unsupported constructs.
The .mmd files remain canonical; render outputs are generated, not hand edited.
"""
from pathlib import Path
from xml.sax.saxutils import escape
import re
import textwrap

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'sequence'
DST = ROOT / 'render'
DST.mkdir(exist_ok=True)
SIMPLE='font-family="DejaVu Sans,Arial,sans-serif"'

def label(t):
    return escape(t, {'"': '&quot;', "'": '&apos;'})

def svg_text(x,y,t,kind='normal',anchor='middle'):
    size={'normal':14,'small':13,'participant':18,'title':27,'fragment':14,'note':14}[kind]
    col={'title':'#112d48','fragment':'#28475b','participant':'#13304a',
         'normal':'#213447','small':'#4a5e70','note':'#23425b'}[kind]
    return f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" fill="{col}" font-size="{size}" {SIMPLE}>{label(t)}</text>'

def wrap_by_pixels(s, limit):
    # Nearly conservative width estimate for Cyrillic 14px sans serif.
    char=max(18, int(limit/8.4))
    if len(s)<=char: return [s]
    chunks=[]
    while s:
        if len(s)<=char: chunks.append(s); break
        pos=s.rfind(' ',0,char+1)
        if pos<=char*0.55: pos=char
        chunks.append(s[:pos].strip()); s=s[pos:].strip()
    return chunks

def render_file(f):
    lines=f.read_text(encoding='utf-8').splitlines()
    title=f.stem
    participants=[]
    names={}
    events=[]
    for n,line in enumerate(lines,1):
        s=line.strip()
        if s.startswith('%% title: '): title=s[10:]; continue
        if not s or s.startswith('%%') or s=='sequenceDiagram': continue
        m=re.fullmatch(r'(actor|participant)\s+(\w+)\s+as\s+(.+)',s)
        if m:
            k,ident,name=m.groups()
            if ident in names: raise ValueError(f'{f}:{n} duplicate {ident}')
            participants.append((ident,name,k)); names[ident]=name
            continue
        if (m:=re.fullmatch(r'(\w+)(-->>|->>)(\w+):\s*(.+)',s)):
            a,arrow,b,message=m.groups()
            if a not in names or b not in names: raise ValueError(f'{f}:{n} undefined participant')
            events.append(('message',a,b,arrow,message));continue
        if (m:=re.fullmatch(r'(activate|deactivate)\s+(\w+)',s)):
            if m.group(2) not in names: raise ValueError(f'{f}:{n} undefined activation')
            events.append((m.group(1),m.group(2)));continue
        if (m:=re.fullmatch(r'(alt|opt|loop|par)\s+(.+)',s)):
            events.append(('begin',m.group(1),m.group(2)));continue
        if (m:=re.fullmatch(r'(else|and)\s+(.+)',s)):
            events.append(('branch',m.group(1),m.group(2)));continue
        if s=='end': events.append(('end',));continue
        if (m:=re.fullmatch(r'Note\s+over\s+(\w+)(?:,(\w+))?:\s*(.+)',s)):
            if m.group(1) not in names or (m.group(2) and m.group(2) not in names): raise ValueError('undefined note participant')
            events.append(('note',m.group(1),m.group(2),m.group(3)));continue
        raise ValueError(f'Unsupported source line {f}:{n}: {s}')
    if len(participants)<2: raise ValueError('too few participants')
    xs={p[0]:155+i*345 for i,p in enumerate(participants)}
    width=xs[participants[-1][0]]+165
    y=171
    plotted=[]
    open_act={p[0]:[] for p in participants}
    acts=[]
    stack=[]
    frags=[]
    for ev in events:
        kind=ev[0]
        if kind=='message':
            a,b=ev[1],ev[2]
            dist=abs(xs[a]-xs[b]);lines=wrap_by_pixels(ev[4], (dist-32) if a!=b else 265)
            y+=max(65, 38+20*len(lines))
            plotted.append(('message',y,a,b,ev[3],lines))
        elif kind=='note':
            lines=wrap_by_pixels(ev[3],360)
            y+=max(64,24+20*len(lines))
            plotted.append(('note',y,ev[1],ev[2],lines))
        elif kind=='activate': open_act[ev[1]].append(y-2)
        elif kind=='deactivate':
            if not open_act[ev[1]]: raise ValueError(f'{f} unmatched deactivate {ev[1]}')
            acts.append((ev[1],open_act[ev[1]].pop(),y+2))
        elif kind=='begin':
            y+=53
            stack.append({'k':ev[1],'label':ev[2],'y1':y-34,'branches':[],'depth':len(stack)})
        elif kind=='branch':
            if not stack: raise ValueError(f'{f} branch outside fragment')
            if ev[1]=='and' and stack[-1]['k']!='par':raise ValueError('and outside par')
            if ev[1]=='else' and stack[-1]['k'] not in ('alt',):raise ValueError('else outside alt')
            y+=50
            stack[-1]['branches'].append((y-23,ev[1]+' '+ev[2]))
        elif kind=='end':
            if not stack:raise ValueError(f'{f} unmatched end')
            y+=38
            fdata=stack.pop();fdata['y2']=y-6;frags.append(fdata)
    if stack: raise ValueError(f'{f} unclosed fragment')
    for k, open_lists in open_act.items():
        if open_lists: raise ValueError(f'{f} unclosed activation {k}')
    if not frags: raise ValueError(f'{f} no fragment')
    if not any(ev[0]=='message' and ev[3]=='-->>' for ev in events): raise ValueError(f'{f} missing return messages')
    height=y+105
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">',
         '<defs><marker id="arr" markerWidth="10" markerHeight="10" refX="7" refY="3" orient="auto"><path d="M0,0 L7,3 L0,6" fill="none" stroke="#255477" stroke-width="1.3"/></marker></defs>',
         f'<rect width="{width}" height="{height}" fill="#fff"/>',
         f'<rect x="0" y="0" width="{width}" height="76" fill="#f0f5f9"/>',svg_text(width/2,49,title,'title')]
    # Fragment backgrounds: outer first, then inner.
    fcolors={'alt':('#f3f8fc','#8baccc'),'opt':('#fffaf0','#c0aa70'),
             'loop':('#f1faf8','#78b5a4'),'par':('#f7f3fc','#a99cca')}
    for fdata in sorted(frags,key=lambda z:z['depth']):
        fill,border=fcolors[fdata['k']]
        x0=44+fdata['depth']*9
        w=width-88-fdata['depth']*18
        out.append(f'<rect x="{x0}" y="{fdata["y1"]}" width="{w}" height="{fdata["y2"]-fdata["y1"]}" rx="8" fill="{fill}" fill-opacity="0.62" stroke="{border}" stroke-width="1.6"/>')
        out.append(f'<rect x="{x0}" y="{fdata["y1"]}" width="72" height="29" rx="6" fill="{border}" fill-opacity="0.23"/>')
        out.append(svg_text(x0+36,fdata['y1']+20,fdata['k'],'fragment'))
        out.append(svg_text(x0+85,fdata['y1']+20,fdata['label'],'small', 'start'))
        for yy,t in fdata['branches']:
            out.append(f'<path d="M{x0} {yy}H{x0+w}" fill="none" stroke="{border}" stroke-width="1.3" stroke-dasharray="8 6"/>')
            out.append(svg_text(x0+15,yy+18,t,'small','start'))
    for key,name,kind in participants:
        x=xs[key]
        out.append(f'<line x1="{x}" x2="{x}" y1="145" y2="{height-45}" stroke="#95a9bb" stroke-width="1.7" stroke-dasharray="7 7"/>')
        fill=('#fcf7ed' if kind=='actor' else '#ebf2f8')
        out.append(f'<rect x="{x-147}" y="96" width="294" height="52" rx="9" stroke="#52718c" stroke-width="1.4" fill="{fill}"/>')
        out.append(svg_text(x,127,name,'participant'))
    # activation layers on top of the fragment/lifeline background.
    for key,y0,y1 in acts:
        x=xs[key]
        out.append(f'<rect x="{x-7}" y="{y0}" width="14" height="{max(7,y1-y0)}" fill="#dceaf5" stroke="#5682a3" stroke-width="1.2"/>')
    for ev in plotted:
        if ev[0]=='message':
            _,yy,a,b,arrow,lines=ev
            xa,xb=xs[a],xs[b]
            yyline=yy+2
            if xa==xb:
                out.append(f'<path d="M{xa+6} {yyline-6} h82 v22 h-82" fill="none" stroke="#255477" stroke-width="1.7" marker-end="url(#arr)"/>')
                mid=xa+72
                lab_y=yy-20
            else:
                d='8 6' if arrow=='-->>' else '0'
                a1=xa+(9 if xb>xa else -9);b1=xb-(9 if xb>xa else -9)
                out.append(f'<path d="M{a1} {yyline} L{b1} {yyline}" stroke="#255477" stroke-width="1.8" stroke-dasharray="{d}" marker-end="url(#arr)"/>')
                mid=(xa+xb)/2;lab_y=yy-14-(len(lines)-1)*18
            lab_width=min(width-80, max(len(t)*8.0 for t in lines)+18)
            out.append(f'<rect x="{mid-lab_width/2}" y="{lab_y-16}" width="{lab_width}" height="{len(lines)*18+8}" rx="4" fill="white" fill-opacity=".96"/>')
            for k,line in enumerate(lines):
                out.append(svg_text(mid,lab_y+k*18,line,'normal'))
        elif ev[0]=='note':
            _,yy,a,b,lines=ev
            xx=(xs[a]+xs[b or a])/2
            w=max(240,min(500,max(len(t)*8.3 for t in lines)+28))
            h=20*len(lines)+20
            out.append(f'<rect x="{xx-w/2}" y="{yy-h+2}" width="{w}" height="{h}" rx="5" fill="#fff7da" stroke="#c5ad66"/>')
            for k,t in enumerate(lines):out.append(svg_text(xx,yy-h+26+k*19,t,'note'))
    out.append(svg_text(width/2,height-30,'Рендер із Mermaid sequenceDiagram · джерело: '+f.name,'small'))
    out.append('</svg>')
    svg_path=DST/(f.stem+'.svg')
    svg_path.write_text('\n'.join(out),encoding='utf8')
    try:
        import cairosvg
        cairosvg.svg2png(bytestring='\n'.join(out).encode(),write_to=str(DST/(f.stem+'.png')),output_width=1800 if width>1800 else width)
    except ImportError:
        pass
    return {'file':f.name,'participants':len(participants),'fragments':len(frags),'returns':sum(1 for q in plotted if q[0]=='message' and q[4]=='-->>'),'canvas':f'{width}x{height}'}

if __name__=='__main__':
    import json
    print(json.dumps([render_file(f) for f in sorted(SRC.glob('S-*.mmd'))],ensure_ascii=False,indent=2))
