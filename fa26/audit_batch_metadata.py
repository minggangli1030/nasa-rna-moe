"""Read-only metadata inventory for the PI's proposed batch-adversarial pilot."""
from pathlib import Path
import json,re
import pandas as pd
R=Path(__file__).resolve().parent;A=R/'artifacts';O=A/'batch_metadata_audit_2026-09-14';O.mkdir(exist_ok=True)
parts=[]
for folder in ['general_survey_2026-09-12','muscle_repeat_flight_2026-09-12','pathway_onboard_1g_2026-09-13']:
 d=pd.read_csv(A/folder/'manifest.csv').fillna('')
 if 'role' in d:d=d[d.role=='primary']
 if 'condition_name' not in d:d['condition_name']=d.condition.map({0:'ground',1:'flight',2:'post-flight'}).fillna('unknown')
 parts.append(d[['study','sample','species','tissue','condition_name','unit']].assign(survey_source=folder))
m=pd.concat(parts,ignore_index=True);assert len(m)==585;assert not m.duplicated(['study','sample']).any()
# GEO metadata already cached for the general survey.
metadata={}
for f in (A/'general_survey_2026-09-12').glob('GSE*_metadata.csv'):
 d=pd.read_csv(f).fillna('')
 for row in d.to_dict('records'):metadata[row['gsm']]=row
# Parse official GEO SOFT records for the later muscle-chip flight.
current={}
for line in (A/'muscle_repeat_flight_2026-09-12/GSE298393_samples.soft').read_text().splitlines()+['^SAMPLE = END']:
 if line.startswith('^SAMPLE = '):
  if current:metadata[current['gsm']]=current
  current={'gsm':line.split(' = ',1)[1]}
 elif line.startswith('!Sample_') and ' = ' in line:
  key,value=line.split(' = ',1);key=key[len('!Sample_'):];current[key]=(current[key]+' | '+value) if key in current else value
fields=['platform_id','instrument_model','library_strategy','library_source','library_selection']
for field in fields:m[field]=[metadata.get(s,{}).get(field,'') if species=='human' else '' for s,species in zip(m['sample'],m.species)]
mouse=pd.read_csv(R.parent/'su26/data/osdr/metadata_new.csv',low_memory=False).fillna('');fields_mouse=['id.assay name','library_type','study.parameter value.sample preservation method','study.parameter value.carcass preservation method'];key=['id.accession','id.sample name'];lookup={}
for k,g in mouse.groupby(key):
 lookup[k]={f:' | '.join(sorted(set(str(v).strip() for v in g[f] if str(v).strip()))) for f in fields_mouse}
for field in fields_mouse:m[field]=[lookup.get((r.study,r.sample),{}).get(field,'') if r.species=='mouse' else '' for r in m.itertuples()]
m.to_csv(O/'selected_sample_metadata.csv',index=False)
rows=[]
for study,g in m[m.species=='human'].groupby('study'):
 rows.append({'study':study,'selected_samples':len(g),'tissue':' | '.join(sorted(set(g.tissue))),'conditions':' | '.join(sorted(set(g.condition_name))),**{f:' | '.join(sorted(set(g[f])-{''})) for f in fields},'instrument_varies_within_study':g.instrument_model.nunique()>1})
pd.DataFrame(rows).to_csv(O/'human_study_technical_summary.csv',index=False)
unknown={'','unknown','not applicable','not available','{not available}','na','n/a','nan','none'};coverage=[]
for species,g in m.groupby('species'):
 for field in fields+fields_mouse:
  v=g[field].astype(str).str.strip();known=~v.str.lower().isin(unknown);coverage.append({'species':species,'field':field,'samples':len(g),'nonempty_known_samples':int(known.sum()),'unique_known_values':int(v[known].nunique()),'interpretation':'technical platform proxy, not actual preparation/run batch' if field in fields else 'assay/protocol context; not automatically a removable technical effect'})
pd.DataFrame(coverage).to_csv(O/'field_availability.csv',index=False)
summary={'status':'metadata inventory complete; no fine-tuning started','selected_biological_samples':len(m),'human_samples':int((m.species=='human').sum()),'mouse_samples':int((m.species=='mouse').sum()),'human_studies':len(rows),'all_human_studies_have_one_recorded_instrument':all(not r['instrument_varies_within_study'] for r in rows),'no_explicit_run_or_preparation_batch_columns_in_cached_mouse_table':not any(re.search(r'batch|sequencing.run|library.preparation',c,re.I) for c in mouse.columns),'mouse_full_metadata_rows':len(mouse),'cautions':['Missing fields mean unavailable in this cached table, not absent from all original records.','Platform/study associations with tissue and flight protocols are not evidence of purely technical batch effects.','Source reprocessing of the same biological sample is not independent replication.']}
(O/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(pd.DataFrame(rows).to_string(index=False));print(json.dumps(summary,indent=2))
