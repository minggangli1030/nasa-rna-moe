# Martin Li: Mixture-of-Experts Models for Spaceflight Transcriptomic Classification

**Audience:** NASA / AI4LS, nontechnical
**Length:** approximately 5½ minutes, leaving 30 seconds of buffer
**Order:** introduction → proposal → key result → limitation → impact → future work

## Slide 1 — Introduction (0:00–0:30)

### Martin Li

**Mixture-of-Experts Models for Spaceflight Transcriptomic Classification**

- Rising third-year at UC Berkeley
- Computer Science and Applied Mathematics
- Previous research: automated patient-speech processing at Berkeley AI Research

**Say:**
“Hi, I’m Martin Li, a rising third-year at UC Berkeley studying computer science and
applied mathematics. I previously researched automated patient-speech processing at
Berkeley AI Research. This summer, I explored biologically specialized AI models for
spaceflight transcriptomic classification.”

**Visual:** headshot, Berkeley affiliation, and one small RNA graphic. Do not add a
full résumé.

---

## Slide 2 — From two experts to eight (0:30–1:25)

### A positive two-expert test led to a more ambitious eight-expert model

**Previous semester**

- Two species experts: human and mouse.
- They made fewer gene-reconstruction errors than one shared model.

**This summer**

- Scale from two species experts to eight human-organ experts.
- Let the model choose the organ expert automatically.
- Test whether reconstruction gains help classify biological response.

**Visual:** “2 species experts → 8 organ experts,” followed by a compact hospital
analogy: shared model, specialists, and an automatic front desk.

**Say:**
“The idea is similar to a hospital: instead of asking one general practitioner to do
everything, use a team of specialists and a front desk that routes each case
automatically.”

---

## Slide 3 — Key result (1:25–2:15)

### Organ specialists make fewer errors reconstructing hidden genes

- Organ specialists achieved **3.6–3.8% lower reconstruction error** than one general
  model on independent human RNA studies.
- Automatic routing retained approximately **97% of the specialist benefit** without
  requiring an organ label.
- The result covered **821 samples, 63 studies, and 8 organs**, and was positive in all
  three training runs.

**Speaker note—not a fourth on-slide bullet:** organ specialists also beat a comparable
general model in all 15 internal training-data tests. This is a different experiment and
should not be plotted on the same axis as the external result.

**Bottom line**
Specialization helped, and automatic routing made that benefit usable without a supplied
organ label.

**Visual:** reconstruction improvement bars plus a large “97% retained automatically”
summary. Keep the slide entirely positive.

**Delivery note:** speak the 3.7% result and 97% automatic-routing result. Treat the
separate 15-test experiment as optional verbal support rather than another chart.

---

## Slide 4 — Independent diagnosis and limitation (2:15–3:25)

### Reconstruction allowed an average-value shortcut

**Text prediction**

- Example: “The astronaut floated in ___.”
- The surrounding words help identify “orbit,” so context matters.

**RNA reconstruction**

- For many hidden gene values, predicting the gene’s usual average can already lower
  the error.
- This shortcut may miss small differences linked to biological response.

**Observed result**
Reconstruction did not require all the information needed for response classification.
That makes it reasonable that the specialist reconstruction gain did not transfer.

**Visual:** side-by-side missing-word and missing-gene-value examples, separated by a
not-equal sign.

---

## Slide 5 — Impact (3:25–4:05)

### The project produced both a positive result and a tested boundary

- **Tested on new studies:** organ specialists improved RNA reconstruction.
- **Automatically useful:** expert selection kept nearly all of the benefit.
- **Clear limit:** better reconstruction did not guarantee better response
  classification.

**Takeaway**
We now know where biological specialization earns its complexity, where its current
benefit stops, and what to test next.

**Visual:** “Before summer” hypothesis → “After summer” externally evaluated reconstruction result,
known downstream boundary, and measured next intervention.

---

## Slide 6 — Future directions (4:05–5:10)

### Align training with the final biological question

**1. Confirm the strongest result**
Repeat the reconstruction comparison once on a completely untouched dataset.

**2. Train closer to the final question**
Emphasize subtle biological differences within the same tissue—not only typical gene
and tissue patterns.

**3. Build a stronger downstream evaluation**
Use a larger labeled dataset with multiple organs and enough room to detect improvement.

**Advance only if both are true**

- The new model features beat raw measurements, standard compression, and existing RNA
  AI models on the scientific task.
- Organ specialization beats an equally capable general model.

**Closing line:**
“This summer showed that biological specialization can improve how a model learns RNA.
The next step is to align that learning with the biological decisions NASA cares
about.”

**Visual:** two near-term tracks—untouched confirmation and standardized-objective
pilot—feeding into a future spaceflight classification benchmark.

---

## Five-minute cut

- Slide 1: remove the details of prior roles from the spoken version.
- Slide 3: omit the sample and study counts; keep the improvement and routing result.
- Slide 4: shorten the sentence example and go directly to the observed result.
- Slide 5: present only the final takeaway sentence.

## Claims to keep precise

- Say **“lower reconstruction error,”** not simply “more accurate.”
- Say **“externally evaluated, pending untouched confirmation,”** not “confirmed.”
- Say **“the learned representation did not improve classification under this test,”**
  not “it contains no state information.”
- Say **“objective misalignment,”** not “the objective was wrong.”
