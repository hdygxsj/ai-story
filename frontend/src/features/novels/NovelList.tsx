import { FormEvent, useState } from "react";

import type { Novel } from "../../api/novels";
import { createNovel } from "../../api/novels";

type NovelListProps = {
  token: string;
  novels?: Novel[];
  onSelectNovel: (novelId: string) => void;
};

export function NovelList({ token, novels = [], onSelectNovel }: NovelListProps) {
  const [title, setTitle] = useState("New Novel");
  const [localNovels, setLocalNovels] = useState<Novel[]>(novels);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const novel = await createNovel(token, title);
    setLocalNovels((current) => [...current, novel]);
    onSelectNovel(novel.id);
  }

  return (
    <section style={{ display: "grid", gap: 12 }}>
      <h2>Novels</h2>
      <form onSubmit={handleCreate} style={{ display: "flex", gap: 8 }}>
        <input aria-label="Novel title" value={title} onChange={(event) => setTitle(event.target.value)} />
        <button type="submit">Create Novel</button>
        <button type="button" onClick={() => onSelectNovel("demo-novel")}>
          Open demo novel
        </button>
      </form>
      <ul>
        {localNovels.map((novel) => (
          <li key={novel.id}>
            <button type="button" onClick={() => onSelectNovel(novel.id)}>
              {novel.title}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
