import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}

describe("App", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the Chinese product shell", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "AI小说工坊" })).toBeInTheDocument();
    expect(screen.getByText("人机共创小说工作台")).toBeInTheDocument();
    expect(screen.queryByText("番茄风格创作空间")).not.toBeInTheDocument();
  });

  it("starts from a Chinese account workflow without demo shortcuts", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "登录" })).toBeInTheDocument();
    expect(screen.queryByText("Continue in demo mode")).not.toBeInTheDocument();
  });

  it("shows top menu navigation and tenant-style novel management after login", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/auth/login")) {
          return Promise.resolve(jsonResponse({ access_token: "token", token_type: "bearer" }));
        }
        if (url.endsWith("/novels")) {
          return Promise.resolve(jsonResponse([{ id: "novel-1", title: "海灯记", description: "雾港故事" }]));
        }
        return Promise.resolve(jsonResponse([]));
      }),
    );

    render(<App />);
    await user.click(screen.getByRole("button", { name: /登\s*录/ }));

    expect(await screen.findByRole("menuitem", { name: "工作台" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Agent配置" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "记忆" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "确认" })).not.toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "素材" })).toBeInTheDocument();
    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();

    expect(screen.getByRole("button", { name: /小说切换器：海灯记/ })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /小说切换器：海灯记/ }));
    expect(await screen.findByText("管理小说")).toBeInTheDocument();
    expect(screen.getByText("新建小说")).toBeInTheDocument();
    expect(screen.getAllByText("海灯记").length).toBeGreaterThanOrEqual(1);
  });

  it("imports a novel from the management page", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/auth/login")) {
          return Promise.resolve(jsonResponse({ access_token: "token", token_type: "bearer" }));
        }
        if (url.endsWith("/novels/import")) {
          expect(init?.method).toBe("POST");
          return Promise.resolve(jsonResponse({ id: "novel-2", title: "导入书", description: "" }));
        }
        if (url.endsWith("/novels")) {
          return Promise.resolve(jsonResponse([{ id: "novel-1", title: "海灯记", description: "雾港故事" }]));
        }
        return Promise.resolve(jsonResponse([]));
      }),
    );

    render(<App />);
    await user.click(screen.getByRole("button", { name: /登\s*录/ }));
    await user.click(await screen.findByRole("button", { name: /小说切换器：海灯记/ }));
    await user.click(await screen.findByText("管理小说"));
    await user.click(await screen.findByRole("button", { name: /导\s*入小说/ }));
    await user.clear(await screen.findByLabelText("导入小说标题"));
    await user.type(screen.getByLabelText("导入小说标题"), "导入书");
    await user.type(screen.getByLabelText("导入正文"), "# 第一章\n正文");
    await user.click(screen.getByRole("button", { name: /^导\s*入$/ }));

    expect(await screen.findByLabelText("章节名称")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /小说切换器：导入书/ })).toBeInTheDocument();
  });

  it("exports the selected novel from the tenant menu", async () => {
    const user = userEvent.setup();
    const createObjectURL = vi.fn(() => "blob:novel");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", { createObjectURL, revokeObjectURL });
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/auth/login")) {
          return Promise.resolve(jsonResponse({ access_token: "token", token_type: "bearer" }));
        }
        if (url.endsWith("/novels/novel-1/export?format=markdown")) {
          return Promise.resolve(new Response("# 第一章\n\n正文", { headers: { "Content-Type": "text/markdown" } }));
        }
        if (url.endsWith("/novels")) {
          return Promise.resolve(jsonResponse([{ id: "novel-1", title: "海灯记", description: "雾港故事" }]));
        }
        return Promise.resolve(jsonResponse([]));
      }),
    );

    render(<App />);
    await user.click(screen.getByRole("button", { name: /登\s*录/ }));
    await user.click(await screen.findByRole("button", { name: /小说切换器：海灯记/ }));
    await user.click(await screen.findByText("导出 Markdown"));

    expect(createObjectURL).toHaveBeenCalled();
  });

  it("opens a novel from management back into the workspace", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/auth/login")) {
          return Promise.resolve(jsonResponse({ access_token: "token", token_type: "bearer" }));
        }
        if (url.endsWith("/novels")) {
          return Promise.resolve(jsonResponse([{ id: "novel-1", title: "海灯记", description: "雾港故事" }]));
        }
        return Promise.resolve(jsonResponse([]));
      }),
    );

    render(<App />);
    await user.click(screen.getByRole("button", { name: /登\s*录/ }));
    await user.click(await screen.findByRole("button", { name: /小说切换器：海灯记/ }));
    await user.click(await screen.findByText("管理小说"));
    await user.click(await screen.findByRole("button", { name: /打\s*开/ }));

    expect(await screen.findByLabelText("章节名称")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "我的小说" })).not.toBeInTheDocument();
  });
});
