#!/usr/bin/env bash
set -e

cd "/c/Users/MezbiN/broadcast"
PY="/c/Users/MezbiN/broadcast/.venv/Scripts/python.exe"
RESULTS_FILE="test_runs.log"
echo "Starting test runs at $(date)" > "$RESULTS_FILE"
for i in {1..5}; do
    echo "=== Run $i ===" >> "$RESULTS_FILE"
    OUTPUT=$($PY -m pytest --tb=short 2>&1)
    echo "$OUTPUT" >> "$RESULTS_FILE"
    # Extract summary line
    SUMMARY=$(echo "$OUTPUT" | grep -E "^={5,}.*passed" | tail -1)
    echo "Summary: $SUMMARY" >> "$RESULTS_FILE"
    echo "---" >> "$RESULTS_FILE"
done
echo "Finished at $(date)" >> "$RESULTS_FILE"
echo "Results saved to $RESULTS_FILE"