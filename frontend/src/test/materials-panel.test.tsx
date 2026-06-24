import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";

import { MaterialsPanel } from "../features/workspace/MaterialsPanel";

const originalGetComputedStyle = window.getComputedStyle;

beforeAll(() => {
  vi.spyOn(window, "getComputedStyle").mockImplementation((element: Element) => originalGetComputedStyle(element));
});

afterAll(() => {
  vi.restoreAllMocks();
});

const baseProps = {
  characterAttributes: [
    {
      id: "attr-1",
      character_name: "叶尘",
      attribute_key: "level",
      value: 4,
      unit: "级",
      scope: "current",
    },
  ],
  characterStates: [],
  creativeAssets: [],
  inventoryItems: [
    {
      id: "item-1",
      owner_name: "叶尘",
      item_name: "灵石",
      quantity: 12,
      unit: "枚",
      location_name: "青石镇",
      description: "战利品",
    },
  ],
  mapLocations: [
    {
      id: "map-1",
      name: "青石镇",
      location_type: "town",
      summary: "叶尘觉醒前居住的小镇。",
      parent_name: "东荒",
      coordinates: { x: 12, y: -3 },
      adjacent_location_names: ["黑风岭"],
    },
  ],
  materialChanges: [],
  relationshipEdges: [],
  timelineEvents: [],
};

describe("MaterialsPanel structured story state", () => {
  it("shows character attributes, inventory, and map tabs", async () => {
    const user = userEvent.setup();
    render(<MaterialsPanel {...baseProps} />);

    expect(screen.getByRole("tab", { name: /人物属性 \(1\)/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /背包 \(1\)/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /地图 \(1\)/ })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: /人物属性 \(1\)/ }));
    expect(screen.getByText("level")).toBeInTheDocument();
    expect(screen.getByText("level").closest("p")).toHaveTextContent("4 级");

    await user.click(screen.getByRole("tab", { name: /背包 \(1\)/ }));
    expect(screen.getByText("灵石")).toBeInTheDocument();
    expect(screen.getByText("灵石").closest("article")).toHaveTextContent("12 枚");

    await user.click(screen.getByRole("tab", { name: /地图 \(1\)/ }));
    expect(screen.getByRole("heading", { name: "青石镇" })).toBeInTheDocument();
    expect(screen.getByText(/x: 12/)).toBeInTheDocument();
  });

  it("submits a new character attribute through the panel", async () => {
    const user = userEvent.setup();
    const onUpsertCharacterAttribute = vi.fn().mockResolvedValue(undefined);
    render(<MaterialsPanel {...baseProps} characterAttributes={[]} onUpsertCharacterAttribute={onUpsertCharacterAttribute} />);

    await user.click(screen.getByRole("tab", { name: /人物属性 \(0\)/ }));
    await user.click(screen.getByRole("button", { name: /新增人物属性/ }));

    const dialog = await screen.findByRole("dialog", { name: "新增人物属性" });
    await user.type(within(dialog).getByLabelText("角色"), "苏安灵");
    await user.type(within(dialog).getByLabelText("属性"), "spirit");
    await user.type(within(dialog).getByLabelText("数值"), "8");
    await user.type(within(dialog).getByLabelText("单位"), "点");
    await user.click(within(dialog).getByRole("button", { name: /保\s*存/ }));

    await waitFor(() =>
      expect(onUpsertCharacterAttribute).toHaveBeenCalledWith({
        attribute_key: "spirit",
        character_name: "苏安灵",
        scope: "current",
        unit: "点",
        value: 8,
      }),
    );
  });
});
