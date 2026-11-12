import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { KnowledgePanel, parseKnowledgeText, prepareKnowledgeDocument } from "./KnowledgePanel";

describe("private knowledge document inputs", () => {
  it("imports markdown as plain text and derives an editable safe id", () => {
    expect(parseKnowledgeText("Return policy.md", "# 退货\n质量问题可申请售后。"))
      .toEqual({ document_id: "Return-policy", title: "Return policy", content: "# 退货\n质量问题可申请售后。" });
  });
  it("rejects unsupported, empty, binary or oversized uploads before a request", () => {
    expect(typeof parseKnowledgeText).toBe("function");
    for (const [filename, content] of [["policy.pdf", "text"], ["policy.txt", "  "], ["policy.md", "a\0b"], ["policy.txt", "a".repeat(10001)]]) {
      expect(() => parseKnowledgeText(filename!, content!)).toThrow();
    }
  });
  it("prepares exactly document fields and rejects invalid identifiers", () => {
    expect(prepareKnowledgeDocument({ document_id: " policy.1 ", title: "  规则 ", content: " 内容 " }))
      .toEqual({ document_id: "policy.1", title: "规则", content: "内容" });
    for (const document_id of ["../secret/path", ".", "..", "", "x".repeat(65)]) {
      expect(() => prepareKnowledgeDocument({ document_id, title: "t", content: "c" })).toThrow();
    }
  });
  it("provides an accessible text-only editor, search modes and navigation", () => {
    expect(KnowledgePanel).toBeTypeOf("function");
    const html = renderToStaticMarkup(<KnowledgePanel onClose={() => {}} />);
    expect(html).toContain("知识库");
    expect(html).toContain("text/plain,text/markdown,.txt,.md");
    expect(html).toContain("文档正文");
    expect(html).toContain("混合检索");
    expect(html).toContain("关键词检索");
    expect(html).toContain("向量检索");
    expect(html).toContain("返回对话");
    expect(html).not.toContain('type="password"');
    expect(html).not.toContain("tenant_id");
  });
});
