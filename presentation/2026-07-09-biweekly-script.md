# Talking script — 2026-07-09 biweekly (~10 min, 12 slides)

Numbers and details are on the slides — talk to the story, don't read the slide out loud.

---

**01 — Title**

Hi everyone, I'm Martin. This is Sprint 1 of my SPARC continuation project at NASA Ames — Mixture-of-Experts for spaceflight transcriptomic classification. The short version: can specialized experts model space biology better than one monolithic model, now that the problems that broke our first attempt are actually fixed?

**02 — Background & setup**

Quick context, since this builds on a team project from last semester. Longer missions mean more radiation, microgravity, and circadian disruption — all of which show up in gene expression — but there's no foundation model built for reading that signal, and real spaceflight data is far too scarce to train on directly. So the strategy is pretrain on abundant ground-based data, then transfer to the rare spaceflight domain — that gap is on screen. This was a Berkeley CDSS Data Discovery project with Dr. Alvarado and a few teammates; the pipeline itself — QC, ortholog mapping, normalization, down to a shared gene vocabulary — Brian led. My part picks up at evaluation.

**03 — Zero-shot OSDR evaluation**

Quick note on how this task actually works, since it's the setup for everything that follows: we mask out a random subset of genes in each sample and ask the model to predict those missing values from the rest of the sequence — the number you'll see is how accurately it reconstructs them, a correlation between predicted and true expression. The team had four pretrained variants, and my question was simple: do any of them actually generalize to real spaceflight data? One thing worth calling out before you read too much into these bars: this eval set is entirely mouse data, which is exactly why mouse scores highest and human lowest — that's species match, not noise, which is actually a good sign that the model is learning real biology. Scale helps too — you can see that in the human numbers. But — these numbers look better than they are. Next slide is why.

**04 — Gene-mean collapse**

Same masked-gene task as the last slide, but now I built a quick diagnostic: what if you just predicted the average expression per gene, no model at all? That trivial baseline is the dashed line — and every one of our four variants falls at or below it. So the accuracy wasn't coming from real reconstruction, it was a shortcut. The one lever that actually moved these numbers was scale, not architecture — human data 5k to 20k closed most of the gap.

**05 — The team's first MoE gate**

So — why Mixture of Experts at all? We'd just shown a generalist model learns *some* cross-species biology, even if weakly. The natural next question: if instead of one generalist, you had experts each specialized on one species, would combining them reconstruct better than any generalist alone — and would that same idea extend to other axes, like organ or tissue? That's the premise behind this gate: human, mouse, and mixed experts, frozen, combined through a learned gate. While wiring this up I also caught a real bug — each expert had trained on its own gene ordering, so the gate was combining outputs that weren't even in the same coordinate system.

**06 — The diagnostic that flagged the gate as premature**

Before spending compute actually training that gate, I asked a cheaper question first: if you had a perfect oracle that always picked the best expert per sample, how much would you even gain over just using the single best expert? That's what this chart shows. The gap is essentially nothing on two of three splits, and the one split that did show a gap turned out to be a bug, not a real signal — I'll explain that in a minute. Bottom line for the team at the time: the bottleneck was expert quality, not the routing logic. That's exactly where this SPARC project starts.

**07 — Research question**

So, formally: can Mixture-of-Experts actually improve prediction and interpretability for spaceflight transcriptomics, once the expert-quality problems that invalidated the first attempt are fixed? Three objectives, on screen — build MoE on top of experts that don't collapse, understand how experts specialize across species and tissue, and benchmark with real attention to interpretability, not just a correlation number.

**08 — v2: the fix**

Here's that bug from before: each expert had trained on its own independent gene ordering, so the earlier "gap" I found was really just a species-identity artifact, not the model doing anything clever. The fix was building one shared canonical gene vocabulary so every expert speaks the same coordinate system, plus a deeper architecture, informed by the scale finding from earlier. This sprint was rebuilding all three experts under that fix.

**09 — Setup: infrastructure and rebuilding the experts**

Two practical things enabled this sprint. I moved off the shared Savio queue onto my own dedicated GPU, and split this work into its own standalone repo so I'm not blocked by anyone else's jobs. With that in place, all three v2 experts finished training — numbers and status are on screen.

**10 — Results**

Two things here. First — good news — none of the three v2 experts collapsed to the gene-mean shortcut this time; they're all making real, sample-dependent predictions. Second, the actual headroom question: with the vocabulary bug fixed, how much would an oracle gain over the best single expert? The answer is almost nothing — about the same order of magnitude as the honest splits from before, not the inflated number the bug produced. Mouse already wins almost every sample here, so there's not much left to route between. But there's a more interesting number on this slide: a simple fixed blend of human and mouse predictions beats the best single expert by several times more than the oracle gap does. Smoothing two predictions together apparently helps more than trying to cleverly pick one.

**11 — Related work**

Two papers shaped how I'm thinking about next steps. One does RNA structure prediction by training an ensemble of models and using *disagreement* between them as the signal — if the models agree, trust them; if they don't, that flags an out-of-distribution case and falls back to a simpler method. No learned gate required. The other, CodonMoE, gets big efficiency gains from one shared backbone with a lightweight adapter on top, instead of several fully independent models. Both point at the same lesson for me: my zero-shot eval is fundamentally an in-distribution/out-of-distribution problem, and I've been routing on species identity — which is usually obvious — instead of on disagreement, which is the signal that's actually informative. And the architecture lesson is to stop training three full independent models and instead try one shared backbone with lightweight experts on top.

**12 — Next steps**

So, where does this leave things. The real deliverable of this sprint is that the vocabulary fix turned an inflated, misleading result into an honest one — that's worth more than a shiny number that doesn't replicate. From here: validate that blend result on a proper held-out split instead of the same eval set I found it on; fix the elephant in the room, which is that my eval domain is entirely mouse data, so of course mouse wins — I need an eval set where the right expert isn't obvious in advance to actually test this. And in parallel, keep pushing expert scale, since that's the one lever that's clearly worked so far. Dedicated infrastructure means all of this moves faster from here. Happy to take questions.
