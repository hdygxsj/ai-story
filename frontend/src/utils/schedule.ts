export function throttle<T extends (...args: never[]) => void>(fn: T, waitMs: number): T {
  let lastRun = 0;
  let timeoutId: ReturnType<typeof setTimeout> | null = null;

  const throttled = ((...args: Parameters<T>) => {
    const now = Date.now();
    const remaining = waitMs - (now - lastRun);
    if (remaining <= 0) {
      if (timeoutId) {
        clearTimeout(timeoutId);
        timeoutId = null;
      }
      lastRun = now;
      fn(...args);
      return;
    }
    if (!timeoutId) {
      timeoutId = setTimeout(() => {
        timeoutId = null;
        lastRun = Date.now();
        fn(...args);
      }, remaining);
    }
  }) as T;

  return throttled;
}

export function debounce<T extends (...args: never[]) => void>(fn: T, waitMs: number): T {
  let timeoutId: ReturnType<typeof setTimeout> | null = null;

  const debounced = ((...args: Parameters<T>) => {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
    timeoutId = setTimeout(() => {
      timeoutId = null;
      fn(...args);
    }, waitMs);
  }) as T;

  return debounced;
}

export function createAnimationFrameScheduler() {
  let frameId: number | null = null;

  const schedule = (callback: () => void) => {
    if (frameId !== null) {
      return;
    }
    frameId = requestAnimationFrame(() => {
      frameId = null;
      callback();
    });
  };

  schedule.cancel = () => {
    if (frameId !== null) {
      cancelAnimationFrame(frameId);
      frameId = null;
    }
  };

  return schedule;
}
