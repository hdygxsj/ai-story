import { describe, expect, it } from "vitest";

import { prepareTimelineEvents } from "../features/workspace/timelinePresentation";

describe("prepareTimelineEvents", () => {
  it("deduplicates and sorts volume milestones chronologically", () => {
    const prepared = prepareTimelineEvents([
      {
        id: "vol3",
        title: "第三卷：开宗立派（崛起期）",
        event_time: "第二卷结束后",
        summary: "白墨开宗立派。",
        created_at: "2026-01-03T00:00:00Z",
      },
      {
        id: "vol1",
        title: "第一卷：觉醒前夜（新手期）",
        event_time: "故事开始",
        summary: "叶尘觉醒系统。",
        created_at: "2026-01-01T00:00:00Z",
      },
      {
        id: "vol2-dup",
        title: "第二卷：世界大变（成长期）",
        event_time: "第一卷结束后",
        summary: "重复的第二卷。",
        created_at: "2026-01-04T00:00:00Z",
      },
      {
        id: "vol2",
        title: "第二卷：世界大变（成长期）",
        event_time: "第一卷结束后",
        summary: "异界之门开启。",
        created_at: "2026-01-02T00:00:00Z",
      },
    ]);

    expect(prepared).toHaveLength(3);
    expect(prepared.map((item) => item.id)).toEqual(["vol1", "vol2-dup", "vol3"]);
    expect(prepared.map((item) => item.title)).toEqual([
      "第一卷：觉醒前夜（新手期）",
      "第二卷：世界大变（成长期）",
      "第三卷：开宗立派（崛起期）",
    ]);
  });

  it("uses explicit position when provided", () => {
    const prepared = prepareTimelineEvents([
      {
        id: "late",
        title: "第三卷",
        event_time: "后期",
        summary: "结局。",
        position: 3,
        created_at: "2026-01-03T00:00:00Z",
      },
      {
        id: "early",
        title: "第一卷",
        event_time: "开篇",
        summary: "起点。",
        position: 1,
        created_at: "2026-01-01T00:00:00Z",
      },
      {
        id: "middle",
        title: "第二卷",
        event_time: "中期",
        summary: "发展。",
        position: 2,
        created_at: "2026-01-02T00:00:00Z",
      },
    ]);

    expect(prepared.map((item) => item.id)).toEqual(["early", "middle", "late"]);
  });
});
