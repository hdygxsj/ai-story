import { describe, expect, it } from "vitest";

import {
  DEFAULT_GRAPH_VIEW_TRANSFORM,
  GRAPH_SIZE,
  clampGraphZoom,
  graphViewBox,
  zoomGraphAroundCenter,
  zoomGraphAtPoint,
} from "../features/workspace/relationshipGraphView";

describe("relationshipGraphView", () => {
  it("builds a view box from zoom and pan", () => {
    expect(graphViewBox({ zoom: 2, panX: 40, panY: 20 })).toBe(`40 20 ${GRAPH_SIZE / 2} ${GRAPH_SIZE / 2}`);
  });

  it("zooms around the graph center", () => {
    const zoomed = zoomGraphAroundCenter(DEFAULT_GRAPH_VIEW_TRANSFORM, 2);
    const size = GRAPH_SIZE / 2;

    expect(zoomed.zoom).toBe(2);
    expect(zoomed.panX).toBeCloseTo((GRAPH_SIZE - size) / 2, 5);
    expect(zoomed.panY).toBeCloseTo((GRAPH_SIZE - size) / 2, 5);
  });

  it("zooms around a pointer position", () => {
    const zoomed = zoomGraphAtPoint(DEFAULT_GRAPH_VIEW_TRANSFORM, 2, 0.5, 0.5);
    const size = GRAPH_SIZE / 2;

    expect(zoomed.zoom).toBe(2);
    expect(zoomed.panX).toBeCloseTo((GRAPH_SIZE - size) / 2, 5);
    expect(zoomed.panY).toBeCloseTo((GRAPH_SIZE - size) / 2, 5);
  });

  it("clamps zoom levels", () => {
    expect(clampGraphZoom(10)).toBe(3);
    expect(clampGraphZoom(0.1)).toBe(0.5);
  });
});
