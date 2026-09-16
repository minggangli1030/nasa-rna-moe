"""Build three discussion slides using the existing August 17 HTML template."""
from pathlib import Path
import re,json,html
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[2];P=R/'fa26/presentation';A=R/'fa26/artifacts/pathway_onboard_1g_2026-09-13'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':16,'svg.fonttype':'none','text.color':'#141413','axes.labelcolor':'#666660','xtick.color':'#666660','ytick.color':'#666660','axes.edgecolor':'#cccbc8','savefig.transparent':True})
data=pd.read_csv(A/'pathway_contrasts.csv');chartvalues={}

def save(fig,name):
 fig.savefig(P/(name+'.svg'),transparent=True);fig.savefig(P/(name+'.png'),dpi=170,transparent=True);plt.close(fig)

def svg(name):
 s=(P/(name+'.svg')).read_text();return '<div class="chart">'+s[s.index('<svg'):].replace('<svg ','<svg role="img" aria-label="'+html.escape({'muscle-program':'Average oxidative-phosphorylation gene-set expression increases in all four human muscle-chip flight and donor-pool comparisons.','mg63-programs':'MG63 microgravity versus onboard one g: higher TNF NF-kB and inflammatory-response gene-set expression, lower DNA-repair gene-set expression.'}[name])+'" ',1)+'</div>'

# A chart of gene-set averages, not a functional activity measurement.
cons=['GSE234465|YA','GSE234465|OS','GSE298393|YA','GSE298393|OS'];g=data[data.pathway=='Oxidative Phosphorylation'].set_index('contrast').loc[cons];v=g.zscore_shift.to_numpy();chartvalues['muscle']=[{'contrast':c,'score':float(z)} for c,z in zip(cons,v)]
fig,ax=plt.subplots(figsize=(10.5,4.8));fig.subplots_adjust(left=.1,right=.99,bottom=.23,top=.84);xs=np.array([0,1,2.6,3.6]);ax.bar(xs,v,width=.68,color=['#798C91','#7A8C6F','#798C91','#7A8C6F'],zorder=3)
ax.set_ylim(0,1.35);ax.set_xlim(-.7,4.3);ax.set_yticks([0,.5,1]);ax.set_xticks(xs,['Young / active','Old / sedentary','Young / active','Old / sedentary'],fontsize=15);ax.yaxis.grid(True,color='#cccbc8',lw=.7,zorder=0);ax.tick_params(length=0,pad=9)
for x,z in zip(xs,v):ax.text(x,z+.05,f'+{z:.2f}',ha='center',fontsize=21,weight='bold',color='#141413')
for spine in ['top','right','left']:ax.spines[spine].set_visible(False)
ax.text(0,1.16,'Average gene-set score: flight − ground',transform=ax.transAxes,fontsize=18,color='#141413');ax.text(.24,-.31,'Flight 1 · GSE234465',transform=ax.transAxes,ha='center',fontsize=15);ax.text(.76,-.31,'Flight 2 · GSE298393',transform=ax.transAxes,ha='center',fontsize=15);save(fig,'muscle-program')
# Three retained MG63 programs, selected from the fully reported ten-set panel.
names=['TNF-alpha Signaling via NF-kB','Inflammatory Response','DNA Repair'];g=data[(data.contrast=='GSE224805|microgravity_vs_onboard_1g|author')].set_index('pathway').loc[names];v=g.zscore_shift.to_numpy();chartvalues['mg63']=[{'pathway':n,'score':float(z)} for n,z in zip(names,v)]
fig,ax=plt.subplots(figsize=(10.5,4.8));fig.subplots_adjust(left=.39,right=.93,bottom=.22,top=.84);ys=np.arange(3);ax.barh(ys,v,height=.48,color=['#7A8C6F','#7A8C6F','#798C91'],zorder=3);ax.set_yticks(ys,['TNF / NF-kB\nsignaling genes','Inflammatory\nresponse genes','DNA repair\ngenes'],fontsize=17);ax.invert_yaxis();ax.set_xlim(-.85,1.1);ax.set_xticks([-.5,0,.5,1],['−0.5','0','+0.5','+1.0']);ax.tick_params(length=0,pad=12);ax.xaxis.grid(True,color='#cccbc8',lw=.7,zorder=0);ax.axvline(0,color='#87867f',lw=1)
for y,z in zip(ys,v):ax.text(z+(.05 if z>0 else -.05),y,f'{z:+.2f}'.replace('-','−'),ha='left' if z>0 else 'right',va='center',fontsize=21,weight='bold')
for spine in ['top','right','left']:ax.spines[spine].set_visible(False)
fig.text(.04,.91,'Average gene-set score: microgravity − onboard 1g',fontsize=18,color='#141413');ax.set_xlabel('Lower expression ←   → Higher expression',fontsize=16,labelpad=14);save(fig,'mg63-programs')
base=(R/'su26/presentation/2026-08-17-final.html').read_text();head=base[:base.index('<body>')];head=re.sub(r'<title>.*?</title>','<title>Two space-biology leads · September 14, 2026</title>',head);nav=base[base.index('<nav class="dots"'):base.index('</body>')]
# Preserve template navigation; additionally synchronize dots after touch/trackpad scrolling.
nav=nav.replace('mark(0);','mark(0);\n  deck.addEventListener("scroll",function(){if(!busy)mark(Math.round(deck.scrollLeft/window.innerWidth))});')
css='''
/* Same visual tokens, typography, surfaces and 180 ms navigation as August 17. */
.slide{padding:28px 3.3vw 78px}.inner,.result .inner{max-width:1760px}
h2{font-size:clamp(34px,3.1vw,58px);line-height:1.09;margin-bottom:18px;max-width:1700px}
.eyebrow{font-size:16px;margin-bottom:13px}.lede{font-size:clamp(20px,1.5vw,28px);max-width:none;margin-bottom:18px}
.result-grid{display:grid;grid-template-columns:70% 30%;align-items:center;gap:0}
.chart{width:100%;padding-right:20px}.chart svg{display:block;width:100%;height:auto;overflow:visible}
.side{padding:8px 0 8px 24px;border-left:1px solid var(--rule)}.side h3{font-size:clamp(23px,1.6vw,30px)}
.side p{font-size:clamp(19px,1.3vw,24px);margin-bottom:14px}.checks-list{list-style:none;margin:16px 0 20px}.checks-list li{font-size:clamp(18px,1.2vw,23px);margin:9px 0}.checks-list li:before{content:'✓';color:var(--sage-deep);font-family:var(--sans);margin-right:10px}
.boundary{font-size:clamp(18px,1.1vw,21px)!important;color:var(--muted);border-top:1px solid var(--rule);padding-top:15px}
.result-note{border-top:1px solid var(--rule);padding-top:13px;font-size:clamp(18px,1.2vw,22px);color:var(--muted);margin-top:12px}
.disclosure{left:3.3vw;right:3.3vw;bottom:47px;font-size:16px;max-width:1760px}
.metric-pair{display:flex;gap:30px;margin:14px 0}.metric-pair strong{display:block;font:700 clamp(32px,2.5vw,46px) var(--sans);color:var(--sage-deep)}.metric-pair span{font-size:18px}
.metric-caption{font:16px/1.4 var(--sans);color:var(--muted);margin-bottom:20px}
.choices{display:grid;grid-template-columns:1fr 1fr;gap:35px;margin:22px 0}.choice{border-top:4px solid var(--sage);padding:22px 24px;background:var(--card);border-radius:0 0 24px 24px}.choice.bone{border-color:var(--blue)}
.choice .tag{font:700 16px var(--sans);letter-spacing:.07em;text-transform:uppercase;color:var(--muted)}.choice h3{font-size:clamp(26px,1.9vw,36px);margin:12px 0 20px}.flow-row{display:grid;grid-template-columns:90px 26px 1fr;align-items:start;gap:14px;padding:14px 0;border-top:1px solid var(--rule)}.flow-row b{font:600 18px var(--sans);padding-top:3px}.flow-row .arrow{color:var(--sage-deep);font:24px var(--sans)}.flow-row p{font-size:clamp(20px,1.3vw,24px);margin:0}.decision{margin-top:18px;background:var(--manilla);border-left:5px solid var(--clay);padding:16px 20px;font-size:clamp(20px,1.4vw,26px)}
.control-cue{display:flex;align-items:center;gap:18px;font-size:19px;border-top:1px solid var(--rule);padding-top:17px;color:var(--muted)}.control-cue b{color:var(--ink)}.control-cue .divider{color:var(--rule)}
.notes{display:none}.notes-panel{position:fixed;inset:10% 12%;background:var(--card);border:2px solid var(--rule);padding:34px 42px;z-index:50;overflow:auto;font-size:25px;line-height:1.6;border-radius:24px}.notes-panel[hidden]{display:none}.notes-panel h3{font-size:30px}.notes-panel button{float:right;border:1px solid var(--rule);background:var(--paper);font:16px var(--sans);padding:8px 13px;cursor:pointer}.notes-panel p{font-size:25px}.keys{position:fixed;left:24px;bottom:12px;font:16px var(--sans);color:var(--muted);z-index:20}
@media(max-width:1300px){.slide{padding:20px 3vw 70px}.eyebrow{margin-bottom:10px}h2{margin-bottom:12px}.lede{margin-bottom:12px}.side{padding-left:18px}.side p{margin-bottom:10px}.checks-list{margin:10px 0 12px}.checks-list li{margin:7px 0}.boundary{padding-top:10px}.metric-pair{margin:10px 0}.metric-caption{margin-bottom:12px}.result-note{margin-top:6px;padding-top:10px}.choices{margin:12px 0;gap:24px}.choice{padding:18px 20px}.choice h3{margin:10px 0 13px}.flow-row{padding:12px 0}.decision{padding:13px 18px;margin-top:14px}.control-cue{font-size:18px;padding-top:12px;gap:12px}.disclosure{bottom:43px}}
@media(max-aspect-ratio:4/3){.deck{display:block;overflow-y:auto;height:100vh}.slide{width:100%;height:auto;min-height:100vh;overflow:visible}.result-grid,.choices{grid-template-columns:1fr}.side{border-left:0;border-top:1px solid var(--rule);padding:20px 0}.disclosure{position:static;margin-top:24px}.chart{padding:0}.control-cue{flex-wrap:wrap}.keys{display:none}}
@page{size:1920px 1080px;margin:0}
@media print{html,body{height:auto;background:var(--paper)}.deck{display:block;overflow:visible;height:auto}.slide{width:1920px;height:1080px;break-after:page;page-break-after:always;padding:28px 3.3vw 78px}.slide:last-child{break-after:auto;page-break-after:auto}.dots,.keys,.notes-panel{display:none!important}.result-grid{grid-template-columns:70% 30%}.choices{grid-template-columns:1fr 1fr}}
'''
head=head.replace('</style>',css+'\n</style>')
notes=[
'''I broadened the survey beyond mouse liver, using frozen BridgeRNA and expression comparisons. We screened ten biological gene sets across sixty primary comparisons. One useful lead came from the human muscle chips: the average expression score for 173 oxidative-phosphorylation genes rises in both flights and both donor pools. These genes are associated with mitochondrial energy production. The direction survives removing individual chips or genes, and changing the expression-processing method. But the individual genes agree only weakly between flights, and the overall profiles still differ. So I would present this as a shared average expression pattern, not proof of increased respiration or one common mechanism.''',
'''The second lead comes from MG63, a bone-like cancer cell line. This experiment compares microgravity with a one-g centrifuge control, both aboard the ISS. In three cultures per group, inflammation-associated gene sets rise and the DNA-repair gene set falls. These directions survive sample removal and comparison with independently processed counts. BridgeRNA also preserves the overall response consistently, as does the expression baseline. The numbers on the right measure agreement between data splits; they are not prediction accuracy. This gives us a cleaner experimental contrast, but it does not yet establish inflammation or impaired repair in healthy bone.''',
'''For the next step, I would choose one of these questions with you. For muscle, we could first inspect the genes driving the shared average and the differences in collection and culture conditions, then ask whether the pattern repeats in a matched independent experiment. For bone, we could look for the inflammation-and-repair expression pattern in another study with onboard one-g controls, ideally using primary cells. The endothelial comparison reminds us why controls matter: its mitochondrial gene-set result is stable against Earth controls but fragile against onboard one-g controls. Which biological question and independent comparison would be most useful to pursue?'''
]
body='''<body>
<main class="deck" id="deck">
<section class="slide result" aria-label="Muscle-chip finding"><div class="inner">
<span class="eyebrow">Space-biology discovery · September 14, 2026 · 1 / Finding</span>
<h2>Muscle chips share an average mitochondrial gene-set <em>increase</em></h2>
<p class="lede">Survey: 10 biological gene sets · 60 primary comparisons · frozen BridgeRNA + expression baseline</p>
<div class="result-grid"><div>'''+svg('muscle-program')+'''</div><aside class="side"><h3>Same direction in all four groups</h3><p>173 genes associated with oxidative phosphorylation—mitochondrial energy production.</p><ul class="checks-list"><li>Remove any one chip</li><li>Remove any one gene</li><li>Change processing / scoring</li></ul><p class="boundary">Individual genes agree weakly across flights. This does <strong>not establish increased respiration</strong>.</p></aside></div>
<p class="result-note">A narrower pattern survives even though the overall expression and model responses differ between flights.</p>
<p class="disclosure">3 chips / condition / pool / flight; shared donor pools. Scores standardized within each comparison; magnitudes are not comparable functional effects.</p>
</div><aside class="notes">'''+html.escape(notes[0])+'''</aside></section>
<section class="slide result" aria-label="Controlled MG63 finding"><div class="inner">
<span class="eyebrow">Space-biology discovery · 2 / Finding · GSE224805</span>
<h2>Onboard 1g controls reveal a <em>stable</em> MG63 response</h2>
<p class="lede">Both groups on the ISS: 3 microgravity cultures ↔ 3 onboard-1g cultures</p>
<div class="result-grid"><div>'''+svg('mg63-programs')+'''</div><aside class="side"><h3>The model retains the response</h3><div class="metric-pair"><div><strong>0.95</strong><span>BridgeRNA mean</span></div><div><strong>0.83</strong><span>Expression</span></div></div><div class="metric-caption">Median split-direction agreement<br>+1 = same direction · 0 = no alignment</div><p>All 9 splits agree in direction for both. Gene-set directions survive sample and source checks.</p><p class="boundary">MG63 is an osteosarcoma-derived cell line. This is a transcriptional lead, not evidence of impaired DNA repair.</p></aside></div>
<p class="result-note">Discuss an inflammation / repair-associated response under a more closely matched flight control.</p>
<p class="disclosure">Three highlighted sets from the ten-set panel. Alternate processing: 5 matched samples. Split agreement is not prediction accuracy or proof of model superiority.</p>
</div><aside class="notes">'''+html.escape(notes[1])+'''</aside></section>
<section class="slide" aria-label="Next research decision"><div class="inner">
<span class="eyebrow">Space-biology discovery · 3 / Next decision</span>
<h2>Choose one biological question and an <em>independent</em> test</h2>
<p class="lede">Two preliminary leads; each needs a different follow-up.</p>
<div class="choices"><article class="choice"><span class="tag">Option A · Human muscle</span><h3>What drives the shared gene-set average?</h3><div class="flow-row"><b>Audit</b><span class="arrow">→</span><p>Member genes, donor pools and culture / collection conditions</p></div><div class="flow-row"><b>Test</b><span class="arrow">→</span><p>Another flight under matched conditions</p></div><div class="flow-row"><b>Advance if</b><span class="arrow">→</span><p>The direction repeats with interpretable gene-level support</p></div></article>
<article class="choice bone"><span class="tag">Option B · Human bone cells</span><h3>Does the controlled MG63 pattern recur?</h3><div class="flow-row"><b>Audit</b><span class="arrow">→</span><p>Inflammatory and DNA-repair gene-set members</p></div><div class="flow-row"><b>Test</b><span class="arrow">→</span><p>Another onboard-1g study, preferably primary cells</p></div><div class="flow-row"><b>Advance if</b><span class="arrow">→</span><p>The expression directions survive an independent comparison</p></div></article></div>
<div class="control-cue"><b>Why controls matter</b><span>Endothelial mitochondrial gene set:</span><span>Earth control → stable</span><span class="divider">│</span><span>Onboard 1g → fragile</span></div>
<div class="decision"><strong>Mentor discussion:</strong> which question has the clearest biological value and feasible next dataset?</div>
<p class="disclosure">Exploratory associations; no universal flight signature or established pathway function. Choose the follow-up before deeper evaluation or fine-tuning.</p>
</div><aside class="notes">'''+html.escape(notes[2])+'''</aside></section>
</main>
<div class="keys">← → slides · N script</div>
<aside class="notes-panel" id="speaker" role="dialog" aria-modal="true" aria-label="Speaking script" hidden><button id="closeNotes">Close · Esc</button><h3>Speaking script</h3><p id="noteText"></p></aside>
'''
extra='''<script>
(function(){var panel=document.getElementById('speaker'),deck=document.getElementById('deck');function show(){var i=Math.round(deck.scrollLeft/window.innerWidth);document.getElementById('noteText').textContent=document.querySelectorAll('.notes')[i].textContent;panel.hidden=false;document.getElementById('closeNotes').focus()}function close(){panel.hidden=true}document.getElementById('closeNotes').onclick=close;window.addEventListener('keydown',function(e){if(e.key.toLowerCase()==='n'){e.preventDefault();e.stopImmediatePropagation();panel.hidden?show():close()}else if(!panel.hidden){if(e.key==='Escape')close();if(['ArrowRight','ArrowLeft','PageDown','PageUp',' ','Home','End'].includes(e.key)){e.preventDefault();e.stopImmediatePropagation()}}},true)})();
</script>'''
(P/'2026-09-14-discovery.html').write_text(head+body+nav+extra+'</body>\n</html>\n')
(P/'2026-09-14-speaking-script.md').write_text('# Space-biology discovery — short speaking script\n\nThree slides; approximately 3 minutes at a conversational pace.\n\n'+''.join(f'## Slide {i+1} — {title}\n\n{note}\n\n' for i,(title,note) in enumerate(zip(['Muscle-chip finding','Controlled MG63 finding','Choose the next test'],notes)))+'## If asked about the numbers\n\n- A gene-set score averages standardized gene expression within each comparison; it is not a fold change or a functional measurement.\n- Split-direction agreement is cosine similarity between response vectors from balanced subsets; +1 means alignment. The overlapping splits are robustness checks, not independent experiments.\n- All ten gene sets, including failed checks, are in the [full report](../artifacts/pathway_onboard_1g_2026-09-13/REPORT.md).\n- Model checkpoint: frozen BridgeRNA r7hnr92k, latest available in the inspected author source. These pathway labels come from expression analysis, not model attribution.\n')
(P/'2026-09-14-chart-values.json').write_text(json.dumps(chartvalues,indent=2)+'\n')
print('Built three slides, two source-derived charts and a',sum(len(n.split()) for n in notes),'word speaking script.')
