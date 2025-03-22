#!/usr/bin/env bash

export MOCK_PORT_API='1'
export THIRD_PARTY_LATENCY_MS=10
export ENTITY_AMOUNT=35000
export THIRD_PARTY_BATCH_SIZE=500

branch=$1
iterations=10

SCRIPT_BASE="$(cd -P "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd -P "${SCRIPT_BASE}/../" && pwd)"



# Validate input
if [[ -z $branch ]]; then
    echo "Error: Please supply a branch or multiple branches."
    exit 1
fi

branches=('main' "$branch")
declare -A branches_map
declare -A aggregation_results

max_branch_length=0

for _branch in "${branches[@]}"; do
    branch_md5=$(echo -n "$_branch" | md5sum | cut -d' ' -f1)
    branches_map["$_branch"]=$branch_md5
    branches_map["$branch_md5"]=$_branch

    # Update max_branch_length for table formatting
    branch_length=${#_branch}
    if (( branch_length > max_branch_length )); then
        max_branch_length=$branch_length
    fi

    git checkout "$_branch" || echo "Error: Failed to checkout branch $_branch."


    echo "Building: $_branch"
    make -f $ROOT_DIR/Makefile build

    echo "Branch: $_branch - MD5: $branch_md5"
    for i in $(seq $iterations); do
        echo "Running $_branch iteration $i"
        export SMOKE_TEST_SUFFIX="$branch_md5-iteration-$i"
        export OCEAN__INTEGRATION__CONFIG__THIRD_PARTY_LATENCY_MS=0

        "$SCRIPT_BASE/run-local-perf-test.sh"
        sleep 10
    done
done

for f in "$ROOT_DIR"/perf-test-results*; do
    if [[ ! -f $f ]]; then
        echo "Warning: No performance result files found."
        continue
    fi

    branch_md5=$(echo "$f" | cut -d'-' -f4)
    duration=$(grep -i 'Duration' "$f" | cut -d'|' -f3 | cut -d' ' -f3)
    branch_name=${branches_map[$branch_md5]}

    if [[ -z $branch_name ]]; then
        echo "Warning: Branch MD5 $branch_md5 not found in branches map. Skipping file $f."
        continue
    fi

    # Ensure duration is numeric
    if ! [[ $duration =~ ^[0-9]+$ ]]; then
        echo "Warning: Invalid duration in file $f. Skipping."
        continue
    fi

    previous_min=${aggregation_results["$branch_name.min"]:-9999}
    previous_max=${aggregation_results["$branch_name.max"]:-0}
    previous_duration=${aggregation_results["$branch_name.duration"]:-0}

    aggregation_results["$branch_name.duration"]=$((previous_duration + duration))

    if (( duration > previous_max )); then
        aggregation_results["$branch_name.max"]=$duration
    fi
    if (( duration < previous_min )); then
        aggregation_results["$branch_name.min"]=$duration
    fi
done

# Adjust table size dynamically
header_length=$((max_branch_length + 2))
table_format="%-${header_length}s | %-10s | %-10s | %-10s\n"

# Generate pretty summary table
printf "\n${table_format}" "Branch Name" "Total Time" "Max" "Min"
printf "${table_format}" "$(printf '%.0s-' $(seq $header_length))" "----------" "----------" "----------"

for branch_name in "${branches[@]}"; do
    total_duration=${aggregation_results["$branch_name.duration"]:-0}
    max_duration=${aggregation_results["$branch_name.max"]:-0}
    min_duration=${aggregation_results["$branch_name.min"]:-0}
    printf "${table_format}" "$branch_name" "$(( $total_duration/$iterations ))" "$max_duration" "$min_duration"
    printf "${table_format}" "$(printf '%.0s-' $(seq $header_length))" "----------" "----------" "----------"

done
rm -f "$ROOT_DIR"/perf-test-results*
echo "Performance tests completed."
