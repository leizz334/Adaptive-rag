"""Diagnose frozen actual node evidence; labels are never passed to the agent."""

import json
from collections import Counter
from pathlib import Path

HERE=Path(__file__).resolve().parent
CATEGORIES="CONTEXT_MISSING REFERENCE_RESOLUTION_ERROR ENTITY_BINDING_ERROR AMBIGUOUS_REFERENCE WRONG_INTENT WRONG_ROUTING PLANNER_TOOL_OMISSION PLANNER_EXTRA_TOOL PLANNER_WRONG_ORDER PLANNER_TERMINATION_FAILURE TOOL_ARGUMENT_ERROR TOOL_EXECUTION_FAILURE STALE_BUSINESS_STATE MISSING_FRESH_OBSERVATION OUTPUT_SCHEMA_FAILURE FALLBACK_CONTROL_FLOW_ERROR SCORER_CONTRACT_ISSUE TEST_INPUT_CORRUPTION OTHER".split()


def main():
    data=json.loads((HERE/"evidence/r0_reconciliation.json").read_bytes())
    diagnoses=[]
    primary=Counter()
    surplus=Counter()
    for item in data["cases"]:
        case=item["case"]
        errors=[]
        extra=[]
        for turn in item["turns"]:
            i=turn["turn"]
            spec=case["turns"][i].get("trajectory",{})
            context=(turn["initial"]or{}).get("selected_context",{})
            calls=[c for c in item["oracle"]["evidence"]["tool_calls"] if c["turn"]==i]
            allowed=set(spec.get("allowed",[]))|{r["name"] for r in spec.get("required",[])}|{n for path in spec.get("valid_paths",[]) for n in path}
            for call in calls:
                if call["name"] not in allowed:
                    row=dict(turn=i,tool=call["name"],arguments=call["arguments"],success=call["success"],branch="execute_tools planned step",needed_for_goal=False)
                    extra.append(row)
                    surplus[call["name"]]+=1
            if context.get("needs_clarification") and len(spec.get("required",[]))>1:
                errors.append(dict(turn=i,node="ContextBuilder",category="ENTITY_BINDING_ERROR",cause="Two explicit jointly requested read targets are treated as an unresolved singular reference; graph skips Intent/Router/Planner",direct="missing required two reads",evidence_sufficient=True))
            if not context.get("order_id") and not context.get("needs_clarification") and any(not c["success"] and c["failure_kind"]=="invalid_arguments" for c in calls):
                errors.append(dict(turn=i,node="ContextBuilder",category="AMBIGUOUS_REFERENCE" if not turn["initial"].get("messages") else "REFERENCE_RESOLUTION_ERROR",cause="Entity absent and reference form not recognized; no clarification or bound target before graph",direct="Empty order arguments reach tools",evidence_sufficient=True,propagates=["TOOL_ARGUMENT_ERROR","PLANNER_TERMINATION_FAILURE"]))
            plan=(turn["plan"]or{}).get("plan")
            if any(c["turn"]==i for c in extra):
                errors.append(dict(turn=i,node="Planner" if plan else "Executor",category="PLANNER_EXTRA_TOOL",cause="Skill expands fixed get_order+track_shipment sequence outside narrow fullmatch; no per-goal evidence stop",direct="Surplus step fails unchanged trajectory",evidence_sufficient=True))
            required={r["name"] for r in spec.get("required",[])}
            if required=={"search_knowledge"} and not calls and (turn["router"]or{}).get("strategy") in {"single","multi"}:
                final=turn["final_state"]or{}
                errors.append(dict(turn=i,node="Goal/trajectory contract",category="SCORER_CONTRACT_ISSUE",cause="Legitimate RAG retrieve_docs path does not emit registered search_knowledge tool event",direct="Missing required tool in Gold despite retrieval path",evidence_sufficient=True,business_assessment=dict(route_legitimate=True,retrieved_chunks=len(final.get("retrieved_chunks",[])),answer_semantics="NOT_ASSESSED_SCRIPTED_GENERATION")))
            if any(c["name"]=="get_order" and c["success"] for c in calls):
                assert turn["initial"] is not None
        if any(r.startswith("missing_observation:") for r in item["oracle"]["reasons"]):
            errors.append(dict(turn=len(item["turns"])-1,node="Executor/Goal Oracle",category="MISSING_FRESH_OBSERVATION",cause="Failed entity binding prevents a new get_order after synthetic state event",direct="Cancelled state observation absent",evidence_sufficient=True,secondary=True))
        assert errors,case["id"]
        # Ordering above follows actual earliest turn and boundary, not symptom count.
        first=errors[0]
        primary[first["category"]]+=1
        nodes=[name for t in item["turns"] for name in t["node_order"]]
        diagnoses.append(dict(case_id=case["id"],first_confirmed_error=first,errors=errors,raw_score_reasons=item["oracle"]["reasons"],surplus_calls=extra,plan_node_invocations=nodes.count("plan_tasks"),executor_node_invocations=nodes.count("execute_tools"),input_integrity="VALID_UTF8_CHINESE",wrong_owner_disclosure=False,business_state_success=item["oracle"]["metrics"]["environment_state_correct"],full_chain_reference="evidence/r0_reconciliation.json#"+case["id"],repair_boundary="Context" if first["node"]=="ContextBuilder" else "Planner" if first["category"]=="PLANNER_EXTRA_TOOL" else "Evaluation dispute; no Gold change"))
    assert sum(len(c["surplus_calls"]) for c in diagnoses)==25
    output=dict(primary_counts={c:primary[c] for c in CATEGORIES},surplus_by_tool=dict(surplus),total_surplus=25,case_diagnoses=diagnoses,provider="OFFLINE_SCRIPTED_NOT_REAL_LLM",classification_rule="One earliest primary category per case; accompanying errors retained, never counted as extra failed tasks")
    (HERE/"evidence/r1_diagnoses.json").write_bytes((json.dumps(output,ensure_ascii=False,indent=2)+"\n").encode())
    lines=["# P2-R1 first-node failure diagnosis","","All16are reexecuted baseline-source offline cases, not real-model conclusions. Full user/history/context/entity source/Intent/Router/plan/tool/result/answer/DB/oracle evidence is linked in R0. One earliest primary error is counted per task. Accompanying score symptoms are retained without counting the same task multiple times.","",f"Primary counts: {dict(primary)}. Surplus25calls by name: {dict(surplus)}.","","## Why environment15/16 can coexist with task0/16","","The committed-state oracle permits unchanged state and finds any matching observation across the whole case. An initial valid read may satisfy it despite a later wrong/missing reference or surplus call. Task success additionally checks every turn's required/allowed/max trajectory, errors and proposal/refusal constraints. Thus environment15/16is neither final-answer accuracy nor per-turn freshness. Only the state-change case lacks a required new observation. No stale state substitution is inferred without an actual new read/answer trace.","","## Cases"]
    for row in diagnoses:
        lines += ["",f"### {row['case_id']}","",f"First: **{row['first_confirmed_error']['category']}** at t{row['first_confirmed_error']['turn']} {row['first_confirmed_error']['node']}. {row['first_confirmed_error']['cause']}",f"Direct score failures: `{'; '.join(row['raw_score_reasons'])}`.",f"Surplus: `{json.dumps(row['surplus_calls'],ensure_ascii=False)}`.",f"Accompanying categories: {', '.join(dict.fromkeys(e['category'] for e in row['errors'][1:])) or 'none'}. Plan/execute node invocations: {row['plan_node_invocations']}/{row['executor_node_invocations']} across all turns. Repair boundary: {row['repair_boundary']}. Evidence sufficient for these observed boundaries; real-model generalization remains untested."]
    lines += ["","## Mechanism and independent business judgment","","Fixed skill expansion is the source of surplus steps, rather than an actual looping LangGraph replan: graph routes plan→execute→generate once per business turn. There is no recursive planning loop in these16. The executor runs every planned step even after the current goal already has sufficient evidence; it also runs shipment lookup after deterministic owner rejection. Tools themselves retain live Owner reads, so these repetitions do not show a permission bypass. Unknown-order plans contain empty arguments and fail schema validation instead of clarifying. A bounded same-turn read duplicate guard and parameter validation are justified; no new general autonomous loop is needed.","","Correct header and shipment observations are different capabilities. Shipment tracking already calls get_visible_order, so an extra get_order solely to check the same Owner is unnecessary for shipment-only tasks. Conversely, real transport-history requests need track_shipment and must not be pruned because they contain 状态. Replace full-utterance status templates and unconditional skill ordering with per-goal required evidence, keeping unknown capabilities available to real Planner.","","The ContextBuilder conflates multi-entity explicit requests with singular ambiguity and misses 张-style/no-ID references. History itself is loaded; absence of a selected entity does not establish history retrieval failure. The source-bound entity hint adds status wording even for shipment goals: preserve user semantics separately from grounding, and never use summary state as business authority. Current explicit targets generally override correctly; no executed wrong-order ID or owner leak is observed in this run.","","Three policy turns (nu12,nu13,nu16) use legitimate retrieve_docs paths but frozen Gold requires the registered search_knowledge tool. Original metrics remain unchanged; this is a contract disagreement, not proof of wrong Router. Supplemental business judgment only certifies route/evidence availability; scripted fixed answers and scripted supported judge cannot establish answer semantics. Do not reroute legitimate policy traffic merely to satisfy a tool-event label. New datasets allow optional tool versus RAG policy paths, with the semantic-answer-judge limitation explicit.","","All old16inputs are valid; old12ASCII? corruption is a separate historical issue. No output-schema error, repeated model-planning loop or hard-safety violation is observed here. P2-Q's real Planner512-token truncations and invalid order placeholders are distinct archived real failures; do not infer a real failure rate from this offline trace.","","Required next changes: generic Context provenance/multi-target/clarification repair; task/evidence-aware Planner selection and structural arguments; same-turn bounded read deduplication retaining all permissions/freshness/HITL/idempotency. Each needs independent RED/GREEN and module-separated offline/real controls. No frozen Gold, dataset, max-call or success criterion change."]
    (HERE/"P2-R1_FAILURE_ROOT_CAUSES.md").write_bytes(("\n".join(lines)+"\n").encode())
    print(json.dumps(dict(primary=dict(primary),surplus=dict(surplus),cases=len(diagnoses)),ensure_ascii=False))


if __name__=="__main__":
    main()
