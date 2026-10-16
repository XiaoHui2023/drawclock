from __future__ import annotations

import json
from pathlib import Path

import pytest

from elk_layout import generate_elk_layout
from layout_preview import build_preview_svg
from presentation import ANCHORS, ALIGNMENTS, DrawingOptions
from test_visible_port_geometry_browser import BROWSER, _edge_dump_dom, _result_json


@pytest.mark.skipif(BROWSER is None, reason="headless browser DOM capture is unavailable")
def test_all_anchor_alignment_combinations_have_real_glyph_and_port_clearance(tmp_path):
    library = Path(__file__).resolve().parents[1] / "drawio-lib/drawclock"
    cards = []
    for anchor in ANCHORS:
        for align in ALIGNMENTS:
            config = {"Root <&>\nlong name": {"kind": "gate", "description": "Root note"},
                      "Clock\noutput": {"kind": "clock", "source": "Root <&>\nlong name",
                                          "description": "Output note", "frequencies": ["100\nMHz", "50", "10", "1"]}}
            options = DrawingOptions(description_anchor=anchor, description_align=align,
                                     name_align=align, frequency_align=align,
                                     frequency_headers=("Operating\nfrequency", "SCAN", "BIST", "Custom"))
            document, _ = generate_elk_layout(config, library_path=library, options=options)
            svg = build_preview_svg(document)
            cards.append(f'<section data-case="{anchor}/{align}">{svg}</section>')
    script = r'''
    const failures=[];let ports=0,texts=0;
    const overlap=(a,b)=>Math.max(a.x,b.x)<Math.min(a.x+a.width,b.x+b.width)-.1 && Math.max(a.y,b.y)<Math.min(a.y+a.height,b.y+b.height)-.1;
    for(const card of document.querySelectorAll('section')){
      const svg=card.querySelector('svg'), view=svg.viewBox.baseVal;
      for(const text of svg.querySelectorAll('text')){
        const b=text.getBBox();texts++;
        if(b.x<view.x-.1||b.y<view.y-.1||b.x+b.width>view.x+view.width+.1||b.y+b.height>view.y+view.height+.1) failures.push([card.dataset.case,'cropped',text.textContent]);
      }
      for(const note of svg.querySelectorAll('.node-annotation')){
        for(const body of svg.querySelectorAll('.component')) if(overlap(note.getBBox(),body.getBBox())) failures.push([card.dataset.case,'note-body',note.dataset.nodeId,body.dataset.nodeId]);
      }
      const geoms=[...svg.querySelectorAll('.component-graphic path,.component-graphic polygon,.component-graphic polyline,.component-graphic line,.component-graphic circle')];
      const samples=[];
      for(const geom of geoms){
        const length=geom.getTotalLength(), count=Math.ceil(length/.2), matrix=svg.getScreenCTM().inverse().multiply(geom.getScreenCTM());
        for(let i=0;i<=count;i++) samples.push(geom.getPointAtLength(length*i/count).matrixTransform(matrix));
      }
      for(const edge of svg.querySelectorAll('polyline.edge')){
        const p=edge.points;
        for(const endpoint of [p.getItem(0),p.getItem(p.numberOfItems-1)]){
          ports++;
          const d=Math.min(...samples.map(s=>Math.hypot(s.x-endpoint.x,s.y-endpoint.y)));
          if(d>.35) failures.push([card.dataset.case,'port-detached',d]);
        }
      }
    }
    const pre=document.createElement('pre');pre.id='result';pre.textContent=JSON.stringify({failures,ports,texts,cases:document.querySelectorAll('section').length});document.body.replaceChildren(pre);
    '''
    page = tmp_path / "presentation-combinations.html"
    page.write_text('<meta charset="utf-8"><body>' + ''.join(cards) + '<script>' + script + '</script>', encoding="utf8")
    result = _result_json(_edge_dump_dom(page))
    (tmp_path / "presentation-browser-result.json").write_text(json.dumps(result, indent=2), encoding="utf8")
    assert result["cases"] == 24 and result["ports"] == 48
    assert result["texts"] >= 240
    assert result["failures"] == []
