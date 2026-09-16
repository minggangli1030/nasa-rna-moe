import pandas as pd,re,json
from pathlib import Path
root=Path(__file__).resolve().parents[1];out=root/'fa26/artifacts/general_survey_2026-09-12';out.mkdir(parents=True,exist_ok=True)
d=pd.read_parquet(root/'fa26/bridge-rna-latest/data/manifests/archs4_sample_metadata_v2.5.parquet')
s=pd.read_parquet(root/'fa26/bridge-rna-latest/data/manifests/sample_manifest.parquet')
t=d[['title','source_name_ch1','characteristics_ch1']].fillna('').agg(' | '.join,axis=1)
patterns={'spaceflight':r'\bspace[ -]?flight\b|\bastronaut|\bcosmonaut|international space station|\bspace flown\b|\bflight\s+(?:sample|control|mouse|mice|human)', 'microgravity':r'\bmicro[ -]?gravity\b|\bzero[ -]?gravity\b|\bclinostat|\brandom positioning|\bsimulated\s+weightless', 'analog':r'\bbed[ -]?rest\b|\bhindlimb\s+(?:unload|suspension)|\bhead.down.tilt\b'}
mask=pd.Series(False,index=d.index)
for name,p in patterns.items():d[name]=t.str.contains(p,case=False,regex=True);mask|=d[name]
c=d[mask].merge(s[['gsm','species','split','study_exposure']],on='gsm',how='left');c.to_csv(out/'archs4_space_keyword_hits.csv',index=False)
for (species,gse),g in c.groupby(['species','series_id']):
 print(species,gse,len(g),'train',int((g.split=='train').sum()),'|', ' || '.join(g.title.head(2)), '|',str(g.characteristics_ch1.iloc[0])[:250])
print('HITS',len(c),c.groupby('species').size().to_dict())
summary=c.groupby(['species','series_id'],dropna=False).agg(n_keyword_hits=('gsm','size'),n_train=('split',lambda x:(x=='train').sum()),n_val=('split',lambda x:(x=='val').sum()),n_unseen=('split',lambda x:(x=='unseen').sum()),example_title=('title','first')).reset_index();summary.to_csv(out/'archs4_candidate_studies.csv',index=False)
