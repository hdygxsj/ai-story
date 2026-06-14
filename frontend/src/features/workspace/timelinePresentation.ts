import type { TimelineEvent } from "../../api/materials";

const CN_VOLUME_NUMBERS: Record<string, number> = {
  一: 1,
  二: 2,
  三: 3,
  四: 4,
  五: 5,
  六: 6,
  七: 7,
  八: 8,
  九: 9,
  十: 10,
};

function parseCnOrDigitNumber(raw: string): number | null {
  if (/^\d+$/.test(raw)) {
    return Number(raw);
  }
  if (raw === "十") {
    return 10;
  }
  if (raw.length === 2 && raw[0] === "十" && CN_VOLUME_NUMBERS[raw[1]]) {
    return 10 + CN_VOLUME_NUMBERS[raw[1]];
  }
  if (raw.length === 2 && CN_VOLUME_NUMBERS[raw[0]] && raw[1] === "十") {
    return CN_VOLUME_NUMBERS[raw[0]] * 10;
  }
  return CN_VOLUME_NUMBERS[raw] ?? null;
}

function extractVolumeNumber(text: string): number | null {
  const match = text.match(/第([一二三四五六七八九十\d]+)卷/);
  if (!match) {
    return null;
  }
  return parseCnOrDigitNumber(match[1]);
}

function normalizeTimelineLabel(value: string): string {
  return value.trim().replace(/\s+/g, " ");
}

function timelineEventKey(event: TimelineEvent): string {
  return `${normalizeTimelineLabel(event.title)}::${normalizeTimelineLabel(event.event_time)}`;
}

function timelineSortKey(event: TimelineEvent): [number, number, number] {
  const combined = `${event.event_time} ${event.title}`;
  if (/(故事开始|开篇|序章|起点)/.test(combined)) {
    return [0, 0, Date.parse(event.created_at ?? "") || 0];
  }

  const titleVolume = extractVolumeNumber(event.title);
  const timeVolume = extractVolumeNumber(event.event_time);
  const primary = titleVolume ?? timeVolume ?? 999;
  const secondary = event.event_time.includes("结束后") ? 1 : 0;
  return [primary, secondary, Date.parse(event.created_at ?? "") || 0];
}

export function dedupeTimelineEvents(events: TimelineEvent[]): TimelineEvent[] {
  const latestByKey = new Map<string, TimelineEvent>();
  const sortedByCreatedAt = [...events].sort(
    (left, right) => (Date.parse(left.created_at ?? "") || 0) - (Date.parse(right.created_at ?? "") || 0),
  );
  for (const event of sortedByCreatedAt) {
    latestByKey.set(timelineEventKey(event), event);
  }
  return [...latestByKey.values()];
}

export function sortTimelineEvents(events: TimelineEvent[]): TimelineEvent[] {
  return [...events].sort((left, right) => {
    const [leftPrimary, leftSecondary, leftCreated] = timelineSortKey(left);
    const [rightPrimary, rightSecondary, rightCreated] = timelineSortKey(right);
    if (leftPrimary !== rightPrimary) {
      return leftPrimary - rightPrimary;
    }
    if (leftSecondary !== rightSecondary) {
      return leftSecondary - rightSecondary;
    }
    return leftCreated - rightCreated;
  });
}

export function prepareTimelineEvents(events: TimelineEvent[]): TimelineEvent[] {
  return sortTimelineEvents(dedupeTimelineEvents(events));
}
