import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ExecutionDetails } from "./ExecutionPanel";

describe("actual execution inspection", () => {
  it("renders only provided nodes/plans/tools/memory and labels local retention", () => {
    const html = renderToStaticMarkup(<ExecutionDetails trace={{root_run_id:"root",session_id:"s",availability:{storage:"process_local",ttl_seconds:900},nodes:["planner","tools"],spans:[{id:"1",parent_id:null,name:"node.planner",kind:"chain",status:"ok",latency_ms:12,metadata:{}}],planner_steps:[{step_id:1,tool_name:"get_order",needs_retrieval:false}],tools:[{name:"get_order",success:true}],retrieval:[],memory:{mode:"M2",message_count:2,summary_used:false}}} />);
    expect(html).toContain("get_order"); expect(html).toContain("12"); expect(html).toContain("M2"); expect(html).toContain("单进程");
    expect(html).not.toContain("DeepSeek"); expect(html).not.toContain("生成摘要成功");
  });
});
