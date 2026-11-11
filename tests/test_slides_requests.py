import copy
import json
import re
import sys
import unittest
from pathlib import Path

SKILL=Path(__file__).resolve().parents[1]/'skills/orgchart'
sys.path.insert(0,str(SKILL/'scripts'))
import normalize_org_chart as normalizer
import org_chart_geometry as geometry
import slides_requests as slides


def readback(result):
    pages={}; elements={}
    for chunk in result['presentation_requests']:
        for req in chunk:
            if 'createSlide' in req:
                obj=req['createSlide']['objectId']; pages[obj]={'objectId':obj,'pageElements':[]}
            if 'createShape' in req:
                x=req['createShape']; obj=x['objectId']; e={'objectId':obj,'shape':{'shapeType':x['shapeType'],'text':{'textElements':[]}}}; elements[obj]=e; pages[x['elementProperties']['pageObjectId']]['pageElements'].append(e)
            if 'createTable' in req:
                x=req['createTable']; e={'objectId':x['objectId'],'table':{'rows':x['rows'],'columns':x['columns'],'tableRows':[{'tableCells':[{'text':{'textElements':[]}} for _ in range(x['columns'])]} for _ in range(x['rows'])]}}; elements[x['objectId']]=e; pages[x['elementProperties']['pageObjectId']]['pageElements'].append(e)
            if 'insertText' in req:
                x=req['insertText']; e=elements[x['objectId']]
                text=e['table']['tableRows'][x['cellLocation']['rowIndex']]['tableCells'][x['cellLocation']['columnIndex']]['text'] if 'cellLocation' in x else e['shape']['text']
                text['textElements'].append({'textRun':{'content':x['text']}})
            if 'createLine' in req:
                x=req['createLine']; e={'objectId':x['objectId'],'line':{}}; elements[x['objectId']]=e; pages[x['elementProperties']['pageObjectId']]['pageElements'].append(e)
            if 'updateLineProperties' in req:
                x=req['updateLineProperties']; elements[x['objectId']]['line']['lineProperties']={k:x['lineProperties'][k] for k in ('startConnection','endConnection')}
    return {'slides':list(pages.values())}

class SlidesTests(unittest.TestCase):
    def test_all_starters_layouts_themes(self):
        for starter in ('simple-team','functional-org','future-state-plan'):
            rows=json.loads((SKILL/'examples/starters'/f'{starter}.json').read_text()); data=normalizer.normalize_source(rows,source_kind='flat_json')[0]
            for mode in geometry.MODES:
                geo=geometry.layout(data,mode)
                for theme in slides.THEMES:
                    with self.subTest(starter=starter,mode=mode,theme=theme):
                        out=slides.compile_requests(geo,theme,chunk=11); self.assertEqual(out,slides.compile_requests(geo,theme,chunk=11))
                        seen=set(); created_cards=set(); created_lines=set(); counts={}
                        for chunk in out['presentation_requests']:
                            self.assertLessEqual(len(chunk),11)
                            for req in chunk:
                                for key in ('createSlide','createShape','createLine'):
                                    if key in req:
                                        obj=req[key]['objectId']; self.assertRegex(obj,r'^[A-Za-z0-9_][A-Za-z0-9_:-]{4,49}$'); self.assertNotIn(obj,seen); seen.add(obj)
                                        if key=='createShape': created_cards.add(obj)
                                        if key=='createLine': created_lines.add(obj)
                                if 'updateLineProperties' in req:
                                    lp=req['updateLineProperties']['lineProperties']; self.assertIn(lp['startConnection']['connectedObjectId'],created_cards); self.assertIn(lp['endConnection']['connectedObjectId'],created_cards)
                        expected_cards=[c for p in geo['pages'] for c in slides.cards(p)]; expected_lines=[c for p in geo['pages'] for c in p['connectors']]
                        self.assertEqual(out['summary']['cards'],len(expected_cards)); self.assertEqual(out['summary']['connectors'],len(expected_lines))
                        self.assertTrue(all(slides.card_id(c) in created_cards for c in expected_cards)); self.assertEqual(created_lines,{slides.line_id(c) for c in expected_lines})
                        expected_legend=sum(len({slides.status(e) for e in slides.cards(p) if e.get('type')!='group_summary_card'}) + any(c.get('type')=='matrix_relationship' for c in p['connectors']) for p in geo['pages']); self.assertEqual(out['summary']['legend_items'],expected_legend)
                        read=readback(out); self.assertTrue(all(x[2] for x in slides.verify(geo,read)))
                        if expected_lines:
                            bad=copy.deepcopy(read)
                            line=next(e for p in bad['slides'] for e in p['pageElements'] if 'line' in e); line['line']['lineProperties']['startConnection']['connectionSiteIndex']=99
                            self.assertFalse(all(x[2] for x in slides.verify(geo,bad)))
    def test_existing_deleted_after_creation_and_groups(self):
        rows=json.loads((SKILL/'examples/starters/simple-team.json').read_text()); data=normalizer.normalize_source(rows,source_kind='flat_json')[0]; geo=geometry.layout(data,'compact_hierarchy')
        out=slides.compile_requests(geo,'neutral',existing={'slides':[{'objectId':'old_slide'}]},chunk=7); self.assertEqual(out['presentation_requests'][-1][-1],{'deleteObject':{'objectId':'old_slide'}})
        read=readback(out); page=read['slides'][0]; page['pageElements']=[{'objectId':'group_1','elementGroup':{'children':page['pageElements']}}]; self.assertTrue(all(x[2] for x in slides.verify(geo,read)))
    def test_proto_default_and_styles(self):
        rows=json.loads((SKILL/'examples/starters/future-state-plan.json').read_text())
        geo=geometry.layout(normalizer.normalize_source(rows,source_kind='flat_json')[0], 'compact_hierarchy')
        out=slides.compile_requests(geo,'collibra-2026')
        read=readback(out)
        for page in read['slides']:
            for element in page['pageElements']:
                for connection in element.get('line',{}).get('lineProperties',{}).values():
                    if connection.get('connectionSiteIndex') == 0: connection.pop('connectionSiteIndex')
        self.assertTrue(all(x[2] for x in slides.verify(geo,read)))
        requests=[r for chunk in out['presentation_requests'] for r in chunk]
        self.assertTrue(all(r['createLine']['lineCategory']=='BENT' for r in requests if 'createLine' in r))
        ids={slides.card_id(c) for p in geo['pages'] for c in slides.cards(p)}
        styles=[r['updateTextStyle'] for r in requests if 'updateTextStyle' in r and r['updateTextStyle']['objectId'] in ids]
        self.assertEqual({x['style']['fontSize']['magnitude'] for x in styles if x['textRange']['type']=='ALL'}, {9})
        self.assertEqual({x['style']['fontSize']['magnitude'] for x in styles if x['textRange']['type']=='FIXED_RANGE'}, {10})
        straight=slides.compile_requests(geo,'neutral',connector_category='STRAIGHT')
        self.assertTrue(all(r['createLine']['lineCategory']=='STRAIGHT' for chunk in straight['presentation_requests'] for r in chunk if 'createLine' in r))
    def test_matrix_style_and_table(self):
        rows=json.loads((SKILL/'examples/starters/functional-org.json').read_text())
        data=normalizer.normalize_source(rows,source_kind='flat_json')[0]
        geo=geometry.layout(data,'matrix_relationships')
        out=slides.compile_requests(geo,'collibra-2026')
        req=[r for chunk in out['presentation_requests'] for r in chunk]
        matrix=next(c for p in geo['pages'] for c in p['connectors'] if c['type']=='matrix_relationship')
        style=next(r['updateLineProperties']['lineProperties'] for r in req if r.get('updateLineProperties',{}).get('objectId')==slides.line_id(matrix))
        self.assertEqual(style['dashStyle'],'DOT'); self.assertEqual(style['lineFill']['solidFill']['color'],slides.color('03755F'))
        self.assertTrue(any(r.get('insertText',{}).get('text','').endswith('Dotted line: works with') for r in req))
        people=[{'node_id':str(i),'display_name':'Person '+str(i),'title':'Role','manager_node_id':'' if i==0 else '0','function':'F'+str(i)} for i in range(25)]
        people[0]['dotted_to_node_ids']='24'
        geo=geometry.layout(normalizer.normalize_source(people,source_kind='flat_json')[0],'matrix_relationships')
        out=slides.compile_requests(geo,'neutral'); req=[r for chunk in out['presentation_requests'] for r in chunk]
        self.assertEqual(out['summary']['tables'],1)
        self.assertTrue(any('createTable' in r for r in req))
        self.assertTrue(any(r.get('insertText',{}).get('text')=='Person 0\nRole' for r in req))
        self.assertTrue(all(x[2] for x in slides.verify(geo,readback(out))))
        bad=readback(out); table=next(e['table'] for p in bad['slides'] for e in p['pageElements'] if 'table' in e); table['tableRows'][0]['tableCells'][0]['text']['textElements'][0]['textRun']['content']='Wrong'
        self.assertFalse(all(x[2] for x in slides.verify(geo,bad)))
    def test_status_and_unicode(self):
        card={'data':{'name':'A😀','title':'Role','status':'other','statusLabel':'Leave'}}
        self.assertEqual(slides.card_text(card),'A😀\nRole\nLeave')
        card['data']['context']=True; self.assertEqual(slides.card_text(card),'A😀 (context)\nRole')
