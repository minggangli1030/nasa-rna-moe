from pathlib import Path
import subprocess,concurrent.futures,gzip
out=Path('/Users/minggangli/Projects/nasa-rna/fa26/workstreams/spaceflight/runs/06_controlled_exposure_validation_2026-09-14/sources')
urls=[]
for acc in ['GSE230181','GSE222998']:
 urls.append((f'https://ftp.ncbi.nlm.nih.gov/geo/series/{acc[:-3]}nnn/{acc}/soft/{acc}_family.soft.gz',acc+'_family.soft.gz'))
for num in ['01','02','06','17','36']:
 name=f'GSE230181_BFX{num}_expr.txt.gz';urls.append(('https://ftp.ncbi.nlm.nih.gov/geo/series/GSE230nnn/GSE230181/suppl/'+name,name))
def get(item):
 url,name=item
 subprocess.run(['curl','-fLsS','--retry','2','--max-time','180',url,'-o',str(out/name)],check=True)
 return name,(out/name).stat().st_size
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 for result in pool.map(get,urls):print(result,flush=True)
for name in ['GSE230181_BFX01_expr.txt.gz','GSE230181_BFX17_expr.txt.gz']:
 with gzip.open(out/name,'rt') as f:
  print(name);print(f.readline()[:2500]);print(f.readline()[:1000])
