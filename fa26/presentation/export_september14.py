"""Render the three-slide deck at both presentation sizes and export its PDF."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright
P=Path(__file__).resolve().parent
with sync_playwright() as pw:
 browser=pw.chromium.launch(channel="chrome")
 page=browser.new_page(viewport={'width':1920,'height':1080},device_scale_factor=1)
 page.goto((P/'2026-09-14-discovery.html').as_uri(),wait_until='load',timeout=60000)
 page.evaluate('document.fonts.ready')
 assert page.locator('.slide').count()==3
 checks=[]
 for width,height in [(1920,1080),(1280,720)]:
  page.set_viewport_size({'width':width,'height':height})
  page.keyboard.press('Home');page.wait_for_timeout(220)
  for i in range(3):
   if i:page.keyboard.press('ArrowRight');page.wait_for_timeout(240)
   page.screenshot(path=str(P/f'2026-09-14-slide-{i+1}-{width}.png'))
   result=page.evaluate('''(i)=>{const s=document.querySelectorAll('.slide')[i],f=s.querySelector('.disclosure').getBoundingClientRect(),r=s.getBoundingClientRect();let overflow=[];for(const el of s.querySelectorAll('h2,.lede,.result-grid,.result-note,.choices,.control-cue,.decision')){const b=el.getBoundingClientRect();if(b.top<r.top||b.bottom>f.top-5||b.left<r.left||b.right>r.right+1)overflow.push({element:el.className||el.tagName,bottom:b.bottom,footer:f.top});}return {slide:i+1,width:innerWidth,active:document.querySelectorAll('.dot[aria-current="true"]').length,current:Array.from(document.querySelectorAll('.dot')).findIndex(x=>x.getAttribute('aria-current')==='true'),overflow}}''',i)
   checks.append(result);assert not result['overflow'],result;assert result['current']==i,result
 # Check direct-dot navigation and speaker script without advancing underneath it.
 page.locator('.dot').nth(0).click();page.wait_for_timeout(240);page.keyboard.press('n');assert page.locator('#speaker').is_visible();assert '173' in page.locator('#noteText').inner_text();page.keyboard.press('ArrowRight');assert page.locator('.dot').nth(0).get_attribute('aria-current')=='true';page.keyboard.press('Escape');assert not page.locator('#speaker').is_visible()
 page.set_viewport_size({'width':1920,'height':1080});page.keyboard.press('Home');page.wait_for_timeout(220);page.emulate_media(media='print');page.pdf(path=str(P/'2026-09-14-discovery.pdf'),print_background=True,prefer_css_page_size=True)
 browser.close()
(P/'2026-09-14-render-checks.json').write_text(json.dumps(checks,indent=2)+'\n')
print('Rendered 3 slides at 1920×1080 and 1280×720; navigation/notes/fit checks passed; PDF exported.')
