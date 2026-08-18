# AI4LS final presentation — speaking script

**Target:** 5–7 minutes with deliberate pauses
**Estimated length:** about 525 spoken words

## Slide 1 — Introduction | 0:00–0:30

Hi everyone. I’m Martin Li, a rising third-year at UC Berkeley studying computer
science and applied mathematics.

I previously researched automated patient-speech processing at Berkeley AI Research.

This summer, I studied whether organ-specialist AI models can learn useful patterns
from RNA data.

## Slide 2 — From two experts to eight | 0:30–1:25

This project grew from work I started last semester.

I first tested two species specialists: one for human data and one for mouse data.
They reconstructed hidden gene values better than one shared model.

That positive result motivated a more ambitious question this summer: can the same
idea scale from two species experts to eight human-organ experts?

The idea is like a hospital. One shared model provides general knowledge. Eight organ
specialists provide focused knowledge. A front desk chooses which specialist should
handle each RNA sample.

Training means hiding gene values and asking the model to fill them in. Later, I test
whether what it learned can separate a spaceflight-related response from a normal or
control response.

## Slide 3 — Main result | 1:25–2:15

The first result was positive.

The organ specialists made about 3.6 to 3.8 percent fewer reconstruction errors than
one shared model. This test included 821 new samples from 63 separate studies and eight
organs.

When the correct organ was supplied, the gain was 3.8 percent. When the model chose the
organ itself, the gain was 3.6 percent.

So automatic selection kept about 97 percent of the specialist benefit. The result
also held across all three training runs.

## Slide 4 — Main limitation | 2:15–3:25

Next, I tested whether the reconstruction improvement carried over to the downstream
task: classifying whether an RNA sample showed a spaceflight-related response or a
normal or control response. It did not. I then ran a separate diagnosis to understand
why the improvement stopped there.

Consider a sentence with one missing word: “The astronaut floated in blank.” Nearby
words tell us that “orbit” makes sense. Predicting the word requires context.

RNA reconstruction is different. For many missing gene values, predicting that gene’s
usual average can already reduce the error. The model can take this shortcut instead
of learning the small differences that may signal a biological response.

This explains the gap. The specialists became better at reconstruction, but
reconstruction did not require all the information needed to classify spaceflight
response. It is therefore reasonable that the improvement did not transfer.

## Slide 5 — Impact | 3:25–4:05

This summer established three things.

First, organ specialists improve reconstruction on new studies. Second, automatic
selection keeps nearly all of the benefit. Third, better reconstruction alone does not
guarantee better biological classification.

That gives us both a useful result and a clear limit.

## Slide 6 — Future work | 4:05–5:10

Next, I would do three things.

First, repeat the reconstruction result once on a completely untouched dataset.

Second, change training so the model must pay attention to small biological
differences, rather than relying on typical values.

Third, build a larger response-classification test across multiple organs, with enough
data to measure improvement reliably.

The model should move forward only if its learned features beat the raw measurements,
and only if organ specialists beat an equally capable shared model.

In short, specialization helped the model learn the reconstruction task. The next step
is to make training better match the biological question we want to answer.

Thank you.

## Optional cut

If time is short, omit the two sentences about the three training runs on Slide 3.
