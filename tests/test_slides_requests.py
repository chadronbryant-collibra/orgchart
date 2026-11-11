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
            if 'insertText' in req:
                x=req['insertText']; elements[x['objectId']]['shape']['text']['textElements'].append({'textRun':{'content':x['text']}})
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
                        expected_legend=sum(len({slides.status(e) for e in slides.cards(p) if e.get('type')!='group_summary_card'}) for p in geo['pages']); self.assertEqual(out['summary']['legend_items'],expected_legend)
                        read=readback(out); self.assertTrue(all(x[2] for x in slides.verify(geo,read)))
                        if expected_lines:
                            bad=copy.deepcopy(read)
                            line=next(e for p in bad['slides'] for e in p['pageElements'] if 'line' in e); line['line']['lineProperties']['startConnection']['connectionSiteIndex']=99
                            self.assertFalse(all(x[2] for x in slides.verify(geo,bad)))
    def test_existing_deleted_after_creation_and_groups(self):
        rows=json.loads((SKILL/'examples/starters/simple-team.json').read_text()); data=normalizer.normalize_source(rows,source_kind='flat_json')[0]; geo=geometry.layout(data,'compact_hierarchy')
        out=slides.compile_requests(geo,'neutral',existing={'slides':[{'objectId':'old_slide'}]},chunk=7); self.assertEqual(out['presentation_requests'][-1][-1],{'deleteObject':{'objectId':'old_slide'}})
        read=readback(out); page=read['slides'][0]; page['pageElements']=[{'objectId':'group_1','elementGroup':{'children':page['pageElements']}}]; self.assertTrue(all(x[2] for x in slides.verify(geo,read)))
    def test_status_and_unicode(self):
        card={'data':{'name':'A😀','title':'Role','status':'other','statusLabel':'Leave'}}
        self.assertEqual(slides.card_text(card),'A😀\nRole\nLeave')
        card['data']['context']=True; self.assertEqual(slides.card_text(card),'A😀 (context)\nRole')
