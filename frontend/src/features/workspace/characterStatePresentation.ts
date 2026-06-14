import type { CharacterState } from "../../api/materials";

function normalizeCharacterName(characterName: string): string {
  return characterName.trim();
}

function normalizeScope(scope: string | undefined): string {
  return (scope ?? "current").trim() || "current";
}

function characterStateKey(state: CharacterState): string {
  return `${normalizeCharacterName(state.character_name)}::${normalizeScope(state.scope)}`;
}

export function dedupeCharacterStates(states: CharacterState[]): CharacterState[] {
  const latestByKey = new Map<string, CharacterState>();
  const sortedStates = [...states].sort((left, right) => {
    const leftTime = left.created_at ? Date.parse(left.created_at) : 0;
    const rightTime = right.created_at ? Date.parse(right.created_at) : 0;
    return leftTime - rightTime;
  });
  for (const state of sortedStates) {
    latestByKey.set(characterStateKey(state), state);
  }
  return [...latestByKey.values()].sort((left, right) =>
    normalizeCharacterName(left.character_name).localeCompare(normalizeCharacterName(right.character_name), "zh-CN"),
  );
}
