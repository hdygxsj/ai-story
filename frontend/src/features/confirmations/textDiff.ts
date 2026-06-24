export type DiffLine = {
  type: "equal" | "insert" | "delete";
  value: string;
};

export type DiffDisplaySegment =
  | { kind: "equal"; text: string }
  | { kind: "insert"; text: string }
  | { kind: "delete"; text: string }
  | { kind: "modify"; before: string; after: string };

function splitDiffLines(text: string): string[] {
  if (!text) {
    return [];
  }
  if (text.includes("\n")) {
    return text.split("\n");
  }
  const sentenceLines = text.match(/[^。！？!?；;.!?]+[。！？!?；;.!?]?/g);
  return sentenceLines && sentenceLines.length > 1 ? sentenceLines : [text];
}

function diffLineArrays(beforeLines: string[], afterLines: string[]): DiffLine[] {
  const n = beforeLines.length;
  const m = afterLines.length;
  const dp = Array.from({ length: n + 1 }, () => Array<number>(m + 1).fill(0));

  for (let i = n - 1; i >= 0; i -= 1) {
    for (let j = m - 1; j >= 0; j -= 1) {
      dp[i][j] =
        beforeLines[i] === afterLines[j]
          ? dp[i + 1][j + 1] + 1
          : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }

  const result: DiffLine[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (beforeLines[i] === afterLines[j]) {
      result.push({ type: "equal", value: beforeLines[i] });
      i += 1;
      j += 1;
      continue;
    }
    if (dp[i + 1][j] >= dp[i][j + 1]) {
      result.push({ type: "delete", value: beforeLines[i] });
      i += 1;
      continue;
    }
    result.push({ type: "insert", value: afterLines[j] });
    j += 1;
  }
  while (i < n) {
    result.push({ type: "delete", value: beforeLines[i] });
    i += 1;
  }
  while (j < m) {
    result.push({ type: "insert", value: afterLines[j] });
    j += 1;
  }
  return result;
}

export function toDisplaySegments(lines: DiffLine[]): DiffDisplaySegment[] {
  const segments: DiffDisplaySegment[] = [];
  let index = 0;
  while (index < lines.length) {
    const current = lines[index];
    const next = lines[index + 1];
    if (current.type === "equal") {
      segments.push({ kind: "equal", text: current.value });
      index += 1;
      continue;
    }
    if (current.type === "delete" && next?.type === "insert") {
      segments.push({ kind: "modify", before: current.value, after: next.value });
      index += 2;
      continue;
    }
    if (current.type === "delete") {
      segments.push({ kind: "delete", text: current.value });
      index += 1;
      continue;
    }
    segments.push({ kind: "insert", text: current.value });
    index += 1;
  }
  return segments;
}

export function diffText(before: string, after: string): DiffDisplaySegment[] {
  return toDisplaySegments(diffLineArrays(splitDiffLines(before), splitDiffLines(after)));
}

export function hasDiffChanges(segments: DiffDisplaySegment[]): boolean {
  return segments.some((segment) => segment.kind !== "equal");
}
