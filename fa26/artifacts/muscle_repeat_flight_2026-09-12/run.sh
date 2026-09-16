#!/usr/bin/env bash
set -euo pipefail
cd /media/volume/moe-reboot/fa26_muscle_repeat_flight_20260912
exec 9>job.lock
flock -n 9 || exit 0
if [ -f output/COMPLETE ]; then exit 0; fi
trap 'code=$?; if [ "$code" -ne 0 ]; then printf "failed %s\n" "$code" > phase.txt; touch output/FAILED; fi' EXIT
printf 'inference\n' > phase.txt
if [ ! -f output/INFERENCE_COMPLETE ]; then
/home/exouser/moe-env/bin/python -u general_space_survey.py infer --base /media/volume/moe-reboot/fa26_general_survey_20260912/base --output output --checkpoint /media/volume/moe-reboot/fa26_bridge_inference/model/r7hnr92k/best_model.pt --official /media/volume/moe-reboot/fa26_pattern_pilot_20260911/bridge-rna-latest/upstream_embeddings/src/fm_embed/inference_model.py
fi
printf 'analysis\n' > phase.txt
OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 /home/exouser/moe-env/bin/python -u muscle_repeat_flight.py analyze --output output --baseline /media/volume/moe-reboot/fa26_general_survey_20260912/output
printf 'ready_for_scientific_review\n' > phase.txt
touch output/COMPLETE
