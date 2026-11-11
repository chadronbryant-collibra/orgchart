#!/usr/bin/env python3
"""Compile geometry into native Google Slides requests, or verify readback.

Geometry: org-chart-geometry/v1 JSON with pages[].id, elements[] (card
collision_class, stable_name, box in inches, data), and connectors[].
Readback: read_presentation JSON containing slides[].objectId and pageElements.
Compile writes presentation_requests (ordered request chunks) and summary.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

FIELDS = 'slides(objectId,pageElements(objectId,shape(shapeType,text.textElements.textRun.content),line(lineProperties(startConnection,endConnection)),table(rows,columns,tableRows(tableCells(text.textElements.textRun.content))),elementGroup(children(objectId,shape(shapeType,text.textElements.textRun.content),line(lineProperties(startConnection,endConnection))))))'
VALID = re.compile(r'^[A-Za-z0-9_][A-Za-z0-9_:-]{4,49}$')
THEMES = {
    'collibra-2026': {'ink':'002B40','muted':'4B4B4B','matrix':'03755F','filled':('FFFFFF','DFE6E8','SOLID'),'open':('FFFFFF','03755F','DASH'),'planned':('F0F2F3','03755F','DOT'),'resigned':('FCE6DF','B64B31','SOLID'),'other':('F0F2F3','4B4B4B','SOLID'),'context':('F0F2F3','4B4B4B','SOLID')},
    'neutral': {'ink':'212121','muted':'757575','matrix':'757575','filled':('FFFFFF','E0E0E0','SOLID'),'open':('FFFFFF','757575','DASH'),'planned':('E0E0E0','757575','DOT'),'resigned':('FDECEA','B71C1C','SOLID'),'other':('E0E0E0','757575','SOLID'),'context':('E0E0E0','757575','SOLID')},
}

def ident(value):
    if VALID.fullmatch(value): return value
    safe = re.sub(r'[^A-Za-z0-9_:-]', '_', value)
    return 'org_' + safe[:33] + '_' + hashlib.sha256(value.encode()).hexdigest()[:12]

def color(value):
    return {'rgbColor': {k:int(value[i:i+2],16)/255 for k,i in [('red',0),('green',2),('blue',4)]}}

def props(page, box):
    return {'pageObjectId':page, 'size':{'width':{'magnitude':box['w']*72,'unit':'PT'},'height':{'magnitude':box['h']*72,'unit':'PT'}}, 'transform':{'scaleX':1,'scaleY':1,'translateX':box['x']*72,'translateY':box['y']*72,'unit':'PT'}}

def cards(page): return [e for e in page.get('elements',[]) if e.get('collision_class') == 'card']
def card_id(card): return ident(card.get('google_slides_object_id') or card['stable_name'])
def line_id(line): return ident(line.get('google_slides_object_id') or line['stable_name'])
def status(card):
    d=card.get('data',{})
    return 'context' if d.get('context') or card.get('type') in ('context_card','repeated_context') else d.get('status', 'open' if d.get('kind') == 'open_role' else 'filled')
def card_text(card):
    d=card.get('data',{}); s=status(card)
    name = 'Open role' if s == 'open' else 'Planned' if s == 'planned' else d.get('name','')
    if s == 'context': name += ' (context)'
    text = name + '\n' + d.get('title','')
    if s == 'other': text += '\n' + d.get('statusLabel','')
    return text

def compile_requests(geometry, theme, layout_id=None, existing=None, chunk=400, connector_category="auto"):
    if chunk < 1: raise ValueError('--chunk must be positive')
    palette=THEMES[theme]; requests=[]; used=set(); count={'pages':0,'cards':0,'connectors':0,'tables':0,'legend_items':0}
    def reserve(obj):
        if obj in used: raise ValueError('Duplicate object ID: '+obj)
        used.add(obj); return obj
    def shape(page, obj, box, text, fill, border, dash='SOLID', fontsize=11, ink=None, bold_first=False, shape_type='ROUND_RECTANGLE', title_style=False, name_size=None):
        reserve(obj)
        requests.append({'createShape':{'objectId':obj,'shapeType':shape_type,'elementProperties':props(page,box)}})
        requests.append({'insertText':{'objectId':obj,'insertionIndex':0,'text':text}})
        properties={'shapeBackgroundFill':{'solidFill':{'color':color(fill)}},'outline':{'outlineFill':{'solidFill':{'color':color(border)}},'weight':{'magnitude':1,'unit':'PT'},'dashStyle':dash},'contentAlignment':'MIDDLE'}
        if title_style: properties.update(shapeBackgroundFill={'propertyState':'NOT_RENDERED'},outline={'propertyState':'NOT_RENDERED'})
        requests.append({'updateShapeProperties':{'objectId':obj,'shapeProperties':properties,'fields':'shapeBackgroundFill,outline,contentAlignment'}})
        requests.append({'updateTextStyle':{'objectId':obj,'textRange':{'type':'ALL'},'style':{'fontFamily':'Arial','fontSize':{'magnitude':fontsize,'unit':'PT'},'foregroundColor':{'opaqueColor':color(ink or palette['ink'])}},'fields':'fontFamily,fontSize,foregroundColor'}})
        if bold_first:
            # Slides indexes UTF-16 code units, not Python code points.
            end=len(text.split('\n',1)[0].encode('utf-16-le'))//2
            if end: requests.append({'updateTextStyle':{'objectId':obj,'textRange':{'type':'FIXED_RANGE','startIndex':0,'endIndex':end},'style':dict({'bold':True}, **({'fontSize':{'magnitude':name_size,'unit':'PT'},'foregroundColor':{'opaqueColor':color(palette['ink'])}} if name_size is not None else {})), 'fields':'bold,fontSize,foregroundColor' if name_size is not None else 'bold'}})
        requests.append({'updateParagraphStyle':{'objectId':obj,'textRange':{'type':'ALL'},'style':{'alignment':'START' if title_style else 'CENTER'},'fields':'alignment'}})
    for page in geometry['pages']:
        pid=reserve(ident(page['id'])); count['pages']+=1
        ref={'layoutId':layout_id} if layout_id else {'predefinedLayout':'BLANK'}
        requests.append({'createSlide':{'objectId':pid,'slideLayoutReference':ref}})
        title=page.get('title') or geometry.get('title','Organization chart')
        if geometry.get('as_of'): title += ' | As of ' + str(geometry['as_of'])
        shape(pid,ident(page['id']+'-title'),{'x':0.42,'y':0.22,'w':12.49,'h':0.58},title,'FFFFFF','FFFFFF',fontsize=18,bold_first=True,shape_type='TEXT_BOX',title_style=True)
        # Function panel headings and companion relationship tables carry meaning
        # that is not represented by cards or attached lines.
        for e in page.get('elements', []):
            if e.get('type') == 'function_panel':
                box=e['box']; label=e.get('data', {}).get('name', '')
                shape(pid,ident(e['stable_name']+'-heading'),{'x':box['x'],'y':box['y'],'w':box['w'],'h':0.36},label,'FFFFFF','FFFFFF',fontsize=11,shape_type='TEXT_BOX')
            elif e.get('type') == 'relationship_table':
                rows=e.get('data', {}).get('rows', [])
                obj=reserve(ident(e['stable_name']))
                box=dict(e['box']); box['h']=min(box['h'], 0.4*(len(rows)+1))
                requests.append({'createTable':{'objectId':obj,'rows':len(rows)+1,'columns':3,'elementProperties':props(pid,box)}})
                values=[['From','To','Relationship']]+[[row.get('from_display') or row.get('from',''), row.get('to_display') or row.get('to',''), row.get('label') or row.get('type') or 'Works with'] for row in rows]
                for ri, row in enumerate(values):
                    for ci, value in enumerate(row):
                        loc={'rowIndex':ri,'columnIndex':ci}
                        requests.append({'insertText':{'objectId':obj,'cellLocation':loc,'insertionIndex':0,'text':str(value)}})
                        if ri:
                            requests.append({'updateTextStyle':{'objectId':obj,'cellLocation':loc,'textRange':{'type':'ALL'},'style':{'foregroundColor':{'opaqueColor':color(palette['ink'])}},'fields':'foregroundColor'}})
                requests.append({'updateTextStyle':{'objectId':obj,'cellLocation':{'rowIndex':0,'columnIndex':0},'textRange':{'type':'ALL'},'style':{'bold':True,'foregroundColor':{'opaqueColor':color(palette['ink'])}},'fields':'bold,foregroundColor'}})
                for ci in (1,2):
                    requests.append({'updateTextStyle':{'objectId':obj,'cellLocation':{'rowIndex':0,'columnIndex':ci},'textRange':{'type':'ALL'},'style':{'bold':True,'foregroundColor':{'opaqueColor':color(palette['ink'])}},'fields':'bold,foregroundColor'}})
                requests.append({'updateTableCellProperties':{'objectId':obj,'tableRange':{'location':{'rowIndex':0,'columnIndex':0},'rowSpan':1,'columnSpan':3},'tableCellProperties':{'tableCellBackgroundFill':{'solidFill':{'color':color('F0F2F3')}}},'fields':'tableCellBackgroundFill'}})
                count['tables']+=1
        lookup={e['stable_name']:card_id(e) for e in cards(page)}
        for e in cards(page):
            s=status(e)
            if s not in palette: raise ValueError('Unknown card status: '+s)
            fill,border,dash=palette[s]; box=e['box']
            text=card_text(e); lines=text.split('\n'); limit=30*box['w']/2
            def font(base, line): return round(max(8, min(base, base*limit/max(len(line), 1))), 1)
            size=min(font(9, line) for line in lines[1:]) if len(lines)>1 else 9
            shape(pid,lookup[e['stable_name']],box,text,fill,border,dash,size,palette['muted'],True,name_size=font(10, lines[0]))
            count['cards']+=1
        for line in page.get('connectors',[]):
            lid=reserve(line_id(line)); seg=line['segments']; x1,y1=seg[0]['x1'],seg[0]['y1']; x2,y2=seg[-1]['x2'],seg[-1]['y2']
            ep={'pageObjectId':pid,'size':{'width':{'magnitude':max(abs(x2-x1)*72,0.01),'unit':'PT'},'height':{'magnitude':max(abs(y2-y1)*72,0.01),'unit':'PT'}},'transform':{'scaleX':-1 if x2<x1 else 1,'scaleY':-1 if y2<y1 else 1,'translateX':x1*72,'translateY':y1*72,'unit':'PT'}}
            requests.append({'createLine':{'objectId':lid,'lineCategory':line.get('native_category','BENT') if connector_category == 'auto' else connector_category,'elementProperties':ep}})
            lp={'startConnection':{'connectedObjectId':lookup[line['from']],'connectionSiteIndex':line['google_slides_from_site_index']},'endConnection':{'connectedObjectId':lookup[line['to']],'connectionSiteIndex':line['google_slides_to_site_index']},'lineFill':{'solidFill':{'color':color(palette['matrix'] if line.get('type') == 'matrix_relationship' else (palette['ink'] if theme == 'collibra-2026' else palette['muted']))}},'weight':{'magnitude':1,'unit':'PT'},'dashStyle':'DOT' if line.get('line_style')=='dotted' or line.get('type')=='dotted_line' else 'SOLID','startArrow':'NONE','endArrow':'NONE'}
            requests.append({'updateLineProperties':{'objectId':lid,'lineProperties':lp,'fields':','.join(lp)}})
            requests.append({'updatePageElementsZOrder':{'pageElementObjectIds':[lid],'operation':'SEND_TO_BACK'}}); count['connectors']+=1
        if any(line.get('type') == 'matrix_relationship' for line in page.get('connectors', [])):
            shape(pid,ident(page['id']+'-legend-matrix'),{'x':9.75,'y':7.02,'w':3.1,'h':0.27},'····  Dotted line: works with','FFFFFF','FFFFFF',fontsize=9,ink=palette['matrix'],shape_type='TEXT_BOX',title_style=True)
            count['legend_items']+=1
        present={status(e) for e in cards(page) if e.get('type') != 'group_summary_card'}
        for i,s in enumerate(x for x in ('filled','open','planned','resigned','other','context') if x in present):
            fill,border,dash=palette[s]
            shape(pid,ident(page['id']+'-legend-'+s),{'x':0.42+i*1.75,'y':7.02,'w':1.65,'h':0.27},s.title(),fill,border,dash,9,palette['muted'] if s=='context' else None,shape_type='ROUND_RECTANGLE')
            count['legend_items']+=1
    for slide in (existing or {}).get('slides',[]):
        obj=slide['objectId']
        if obj in used: raise ValueError('Existing slide ID collides with a new object: '+obj)
        requests.append({'deleteObject':{'objectId':obj}})
    count['request_count']=len(requests)
    return {'presentation_requests':[requests[i:i+chunk] for i in range(0,len(requests),chunk)],'summary':count}

def walk(elements):
    for e in elements:
        yield e
        yield from walk(e.get('elementGroup',{}).get('children',[]))

def verify(geometry, readback):
    slides={s['objectId']:s for s in readback.get('slides',[])}; results=[]
    for page in geometry['pages']:
        pid=ident(page['id']); slide=slides.get(pid); results.append(('slide',pid,slide is not None))
        elements={e['objectId']:e for e in walk(slide.get('pageElements',[]))} if slide else {}
        lookup={e['stable_name']:card_id(e) for e in cards(page)}
        for card in cards(page):
            obj=card_id(card); shape=elements.get(obj,{}).get('shape',{}); texts=shape.get('text',{}).get('textElements',[])
            actual=''.join(t.get('textRun',{}).get('content','') for t in texts)
            results.append(('card',obj,shape.get('shapeType')=='ROUND_RECTANGLE' and actual.startswith(card_text(card).split('\n')[0])))
        for table in (e for e in page.get('elements', []) if e.get('type') == 'relationship_table'):
            obj=ident(table['stable_name']); actual=elements.get(obj,{}).get('table')
            ok=actual is not None and actual.get('rows', 0) == len(table.get('data',{}).get('rows',[]))+1 and actual.get('columns', 0) == 3
            if ok and 'tableRows' in actual:
                expected=[['From','To','Relationship']]+[[r.get('from_display') or r.get('from',''),r.get('to_display') or r.get('to',''),r.get('label') or r.get('type') or 'Works with'] for r in table['data']['rows']]
                for ri, row in enumerate(actual['tableRows']):
                    for ci, cell in enumerate(row.get('tableCells',[])):
                        if 'text' in cell:
                            text=''.join(t.get('textRun',{}).get('content','') for t in cell['text'].get('textElements',[]))
                            ok = ok and text.rstrip('\n') == str(expected[ri][ci])
            results.append(('table',obj,ok))
        for line in page.get('connectors',[]):
            obj=line_id(line); element=elements.get(obj,{}); lp=element.get('line',{}).get('lineProperties',{})
            start={'connectedObjectId':lookup[line['from']],'connectionSiteIndex':line['google_slides_from_site_index']}; end={'connectedObjectId':lookup[line['to']],'connectionSiteIndex':line['google_slides_to_site_index']}
            def matches(actual, expected):
                return actual is not None and actual.get('connectedObjectId') == expected['connectedObjectId'] and actual.get('connectionSiteIndex', 0) == expected['connectionSiteIndex']
            results.append(('connector',obj,matches(lp.get('startConnection'), start) and matches(lp.get('endConnection'), end)))
    return results

def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter); sub=parser.add_subparsers(dest='command',required=True)
    c=sub.add_parser('compile',help='Compile geometry JSON into ordered Slides request chunks'); c.add_argument('geometry'); c.add_argument('--theme',required=True,choices=THEMES); c.add_argument('--layout-id'); c.add_argument('--existing-slides',help='read_presentation JSON with slides[].objectId'); c.add_argument('--connector-category',choices=('auto','BENT','STRAIGHT'),default='auto'); c.add_argument('--chunk',type=int,default=400); c.add_argument('--output',required=True)
    v=sub.add_parser('verify',help='Check expected IDs, shape text and attached line endpoints in read_presentation JSON'); v.add_argument('geometry'); v.add_argument('presentation_readback')
    sub.add_parser('fields',help='Print the read_presentation fields mask required by verify')
    a=parser.parse_args()
    try:
        if a.command=='fields': print(FIELDS); return 0
        geometry=json.loads(Path(a.geometry).read_text())
        if a.command=='compile':
            existing=json.loads(Path(a.existing_slides).read_text()) if a.existing_slides else None
            result=compile_requests(geometry,a.theme,a.layout_id,existing,a.chunk,a.connector_category); Path(a.output).write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n'); print(json.dumps(result['summary'],sort_keys=True)); return 0
        results=verify(geometry,json.loads(Path(a.presentation_readback).read_text())); print('RESULT  TYPE       OBJECT ID')
        for typ,obj,ok in results: print(f'{"PASS" if ok else "FAIL":7} {typ:10} {obj}')
        return 0 if all(x[2] for x in results) else 1
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print('Error: '+str(exc),file=sys.stderr); return 1
if __name__=='__main__': sys.exit(main())
