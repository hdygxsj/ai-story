import { useState } from "react";

type DocumentEditorProps = {
  initialText?: string;
  onSelectText?: (text: string) => void;
};

export function DocumentEditor({
  initialText = "Write or paste chapter text here.",
  onSelectText,
}: DocumentEditorProps) {
  const [text, setText] = useState(initialText);

  function handleUseSelection() {
    const selection = window.getSelection()?.toString().trim();
    onSelectText?.(selection || text);
  }

  return (
    <section style={{ display: "grid", gap: 12, padding: 16 }}>
      <div style={{ alignItems: "center", display: "flex", justifyContent: "space-between" }}>
        <h2>Editor</h2>
        <button type="button" onClick={handleUseSelection}>
          Ask AI to rewrite selection
        </button>
      </div>
      <textarea
        aria-label="Document editor"
        value={text}
        onChange={(event) => setText(event.target.value)}
        style={{ minHeight: 420, resize: "vertical", width: "100%" }}
      />
    </section>
  );
}
