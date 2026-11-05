"""Supplementary per-turn business observations; never changes task/Gold scoring."""

BUSINESS_READS = {
    "get_order", "get_order_items", "track_shipment", "get_refund_status",
    "check_inventory", "get_product_detail", "get_warranty", "get_coupon",
}


def fresh_business(rows, cases):
    required=correct=0
    for row in rows:
        for i,turn in enumerate(cases[row["case_id"]].turns):
            if "business_rejected" in turn.expected_failures:
                continue
            for wanted in turn.trajectory.required:
                if wanted.name not in BUSINESS_READS:
                    continue
                required+=1
                matches=[c for c in row["evidence"]["tool_calls"] if c["turn"]==i and c["name"]==wanted.name and c["success"] and c["status"]!="denied" and all(c["arguments"].get(k)==v for k,v in wanted.arguments.items())]
                target=wanted.arguments.get("order_id")
                correct+=bool(matches and all(c["output"].get("status")==turn.state_changes[target] for c in matches) if wanted.name=="get_order" and target in turn.state_changes else matches)
    return dict(fresh_business_correct=correct,fresh_business_required=required,fresh_business_accuracy=correct/required if required else None)
