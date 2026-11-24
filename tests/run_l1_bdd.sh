#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")/.."
export PYTHONPATH="tests:.${PYTHONPATH:+:$PYTHONPATH}"
run_group(){
    case "$1" in
        range)
            python3 -m unittest -v test_wiki_forest.ForestTests.test_preview_counts_pending_trees_from_in_range_targets
            NODE_PATH="${NODE_PATH:+$NODE_PATH:}/usr/share/nodejs" node --test tests/l1_range_bdd.cjs ;;
        timeline) node --test tests/l1_timeline_bdd.cjs tests/test_timeline.cjs tests/test_render_budget.cjs ;;
        memory)
            python3 -m unittest -v test_l1_opinion_bdd.MemoryScenarios
            NODE_PATH="${NODE_PATH:+$NODE_PATH:}/usr/share/nodejs" node --test tests/l1_lineage_bdd.cjs ;;
        documents)
            python3 -m unittest -v test_l1_documents_bdd
            NODE_PATH="${NODE_PATH:+$NODE_PATH:}/usr/share/nodejs" node --test tests/l1_document_reader_bdd.cjs ;;
        compound) python3 -m unittest -v test_l1_opinion_bdd.CompoundScenarios ;;
        *) echo 'Usage: tests/run_l1_bdd.sh [range|timeline|memory|compound|documents|all]' >&2; return 2 ;;
    esac
}
if [[ ${1:-all} == all ]]; then
    for group in range timeline memory compound documents; do run_group "$group"; done
else
    run_group "$1"
fi
