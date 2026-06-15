export const GRAPH_SIZE = 520;
export const MIN_GRAPH_ZOOM = 0.5;
export const MAX_GRAPH_ZOOM = 3;
export const GRAPH_ZOOM_STEP = 0.25;

export type GraphViewTransform = {
  zoom: number;
  panX: number;
  panY: number;
};

export const DEFAULT_GRAPH_VIEW_TRANSFORM: GraphViewTransform = {
  zoom: 1,
  panX: 0,
  panY: 0,
};

export function clampGraphZoom(zoom: number): number {
  return Math.min(MAX_GRAPH_ZOOM, Math.max(MIN_GRAPH_ZOOM, zoom));
}

export function graphViewBox(transform: GraphViewTransform): string {
  const size = GRAPH_SIZE / transform.zoom;
  return `${transform.panX} ${transform.panY} ${size} ${size}`;
}

export function zoomGraphAroundCenter(transform: GraphViewTransform, nextZoom: number): GraphViewTransform {
  const clampedZoom = clampGraphZoom(nextZoom);
  const size = GRAPH_SIZE / transform.zoom;
  const nextSize = GRAPH_SIZE / clampedZoom;
  const centerX = transform.panX + size / 2;
  const centerY = transform.panY + size / 2;

  return {
    zoom: clampedZoom,
    panX: centerX - nextSize / 2,
    panY: centerY - nextSize / 2,
  };
}

export function zoomGraphAtPoint(
  transform: GraphViewTransform,
  nextZoom: number,
  pointerRatioX: number,
  pointerRatioY: number,
): GraphViewTransform {
  const clampedZoom = clampGraphZoom(nextZoom);
  const size = GRAPH_SIZE / transform.zoom;
  const nextSize = GRAPH_SIZE / clampedZoom;
  const svgX = transform.panX + pointerRatioX * size;
  const svgY = transform.panY + pointerRatioY * size;

  return {
    zoom: clampedZoom,
    panX: svgX - pointerRatioX * nextSize,
    panY: svgY - pointerRatioY * nextSize,
  };
}

export function panGraphView(
  transform: GraphViewTransform,
  deltaX: number,
  deltaY: number,
  viewportWidth: number,
  viewportHeight: number,
): GraphViewTransform {
  const size = GRAPH_SIZE / transform.zoom;
  const unitsPerPixelX = size / Math.max(viewportWidth, 1);
  const unitsPerPixelY = size / Math.max(viewportHeight, 1);

  return {
    ...transform,
    panX: transform.panX - deltaX * unitsPerPixelX,
    panY: transform.panY - deltaY * unitsPerPixelY,
  };
}
