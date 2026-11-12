import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import { ExperiencePanel } from "./ExperiencePanel";
it("labels historical qualification and measured benefit without an Active control", () => {
  const html = renderToStaticMarkup(<ExperiencePanel />);
  expect(html).toContain("EXPERIENCE_BENEFIT=NOT_ESTABLISHED");
  expect(html).toContain("离线历史"); expect(html).toContain("人工审批 0");
  expect(html).toContain("E0"); expect(html).toContain("E1"); expect(html).toContain("E2");
  expect(html).not.toContain('role="switch"'); expect(html).not.toContain("在线自学习已启用");
});
