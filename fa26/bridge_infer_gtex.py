#!/usr/bin/env python3
"""Run the available BridgeRNA checkpoint on its bundled GTEx count matrix.

This exploratory utility checks structural input compatibility, converts counts
to canonical log1p(TPM), exports unmasked mean-pooled hidden embeddings, and runs
a separate masked-reconstruction check. The original checkpoint's forward-pass
semantics and training gene-order provenance still require verification.
"""
import argparse, json
from pathlib import Path

import h5py
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from audit_bridge_contract import canonical_genes, aligned_lengths, log1p_tpm, sha256


class RotaryExpressionEmbedding(nn.Module):
    def __init__(self, dim, base=100.0, mask_token=-10.0):
        super().__init__()
        self.mask_token = mask_token
        self.register_buffer("inv_freq", 1 / (base ** (torch.arange(0, dim, 2).float() / dim)))
    def forward(self, x):
        z = torch.einsum("bg,d->bgd", x, self.inv_freq)
        z = torch.cat((z.sin(), z.cos()), dim=-1)
        return z.masked_fill((x == self.mask_token).unsqueeze(-1), 0)


class Layer(nn.Module):
    def __init__(self, d=512, heads=8, ff=2048):
        super().__init__(); self.heads=heads; self.width=d//heads
        self.q_proj=nn.Linear(d,d); self.k_proj=nn.Linear(d,d); self.v_proj=nn.Linear(d,d); self.out_proj=nn.Linear(d,d)
        self.norm1=nn.LayerNorm(d); self.norm2=nn.LayerNorm(d); self.ffn=nn.Sequential(nn.Linear(d,ff),nn.GELU(),nn.Linear(ff,d))
    def forward(self, x):
        b,g,_=x.shape
        h=self.norm1(x)
        q=self.q_proj(h).view(b,g,self.heads,self.width).transpose(1,2)
        k=self.k_proj(h).view(b,g,self.heads,self.width).transpose(1,2)
        v=self.v_proj(h).view(b,g,self.heads,self.width).transpose(1,2)
        a=F.scaled_dot_product_attention(q,k,v,dropout_p=0).transpose(1,2).reshape(b,g,-1)
        x=x+self.out_proj(a); return x+self.ffn(self.norm2(x))


class BridgeRNA(nn.Module):
    def __init__(self):
        super().__init__(); self.gene_embedding=nn.Embedding(15165,512); self.ree=RotaryExpressionEmbedding(512)
        self.layers=nn.ModuleList([Layer() for _ in range(12)]); self.output_map=nn.Linear(512,1)
    def encode(self,x):
        h=self.gene_embedding.weight.unsqueeze(0)+self.ree(x)
        for layer in self.layers: h=layer(h)
        return h
    def forward(self,x):
        h=self.encode(x); return self.output_map(h).squeeze(-1),h


def decode(a): return np.asarray([x.decode() if isinstance(x,bytes) else str(x) for x in a])

def main():
    p=argparse.ArgumentParser(); p.add_argument('--root',type=Path,required=True); p.add_argument('--output',type=Path,required=True)
    p.add_argument('--batch-size',type=int,default=1); p.add_argument('--max-samples',type=int,default=24); p.add_argument('--device',default='cuda'); p.add_argument('--seed',type=int,default=1701); a=p.parse_args()
    if a.max_samples < 1 or a.batch_size < 1: p.error('max-samples and batch-size must be positive')
    root=a.root; model_path=root/'model/r7hnr92k/best_model.pt'; h5_path=root/'data/gtex/gtex_matrix.h5'
    canonical=canonical_genes(root/'data/ensembl/canonical_genes.csv')
    lens=aligned_lengths(root/'data/gencode/gencode_v49_gene_exon_lengths.csv',canonical)
    with h5py.File(h5_path,'r') as f:
        genes=decode(f['meta/genes'][:]); tissue=decode(f['meta/tissue'][:]); ids=decode(f['meta/sampid'][:]); lookup={g:i for i,g in enumerate(genes)}
        index=np.asarray([lookup.get(g,-1) for g in canonical]); found=index>=0
        if len(lookup) != len(genes): raise ValueError('Duplicate GTEx symbols require explicit aggregation')
        if f['data/expression'].shape != (len(ids),len(genes)): raise ValueError('GTEx matrix/metadata shape mismatch')
        if not found.all() or not np.isfinite(lens).all(): raise ValueError(f'gene contract failed: found={found.sum()}/15165, valid_lengths={np.isfinite(lens).sum()}/15165')
        chosen=[]
        for i in range(len(ids)):
            if tissue[i].strip() and tissue[i] not in {tissue[j] for j in chosen}: chosen.append(i)
            if len(chosen)>=a.max_samples: break
        if not chosen: raise ValueError('No samples with nonempty tissue metadata')
        raw=f['data/expression'][chosen,:][:,index].astype(np.float64)
    x=log1p_tpm(raw,lens)
    ckpt=torch.load(model_path,map_location='cpu',weights_only=True); model=BridgeRNA(); model.load_state_dict(ckpt['model_state_dict'],strict=True); model.eval().to(a.device)
    rng=np.random.default_rng(a.seed); mask=rng.random(x.shape)<.15; masked=x.copy(); masked[mask]=-10
    embeddings=[]; predictions=[]
    with torch.inference_mode():
        for start in range(0,len(x),a.batch_size):
            stop=start+a.batch_size
            h=model.encode(torch.from_numpy(x[start:stop]).to(a.device))
            embeddings.append(h.mean(1).float().cpu().numpy()); del h
            pred,h=model(torch.from_numpy(masked[start:stop]).to(a.device))
            predictions.append(pred.float().cpu().numpy()); del pred,h
    pred=np.concatenate(predictions); emb=np.concatenate(embeddings)
    if not np.isfinite(emb).all() or not np.isfinite(pred).all(): raise ValueError('Nonfinite model outputs')
    a.output.parent.mkdir(parents=True,exist_ok=True); np.savez_compressed(a.output,embeddings=emb,sample_ids=np.asarray(ids)[chosen],tissues=np.asarray(tissue)[chosen],input_log1p_tpm=x)
    report={'checkpoint':str(model_path),'n_samples':len(chosen),'genes':len(canonical),'mask_ratio':.15,'seed':a.seed,'device':a.device,'embedding_input':'unmasked log1p(TPM)','pooling':'final-layer mean over all canonical genes','checkpoint_sha256':sha256(model_path),'canonical_sha256':sha256(root/'data/ensembl/canonical_genes.csv'),'forward_semantics_verified':False,'masked_mse':float(np.square(pred[mask]-x[mask]).mean()),'input_min':float(x.min()),'input_max':float(x.max()),'tissues':list(np.asarray(tissue)[chosen])}
    a.output.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2))
if __name__=='__main__': main()
