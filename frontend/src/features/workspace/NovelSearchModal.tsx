import { FileTextOutlined, SearchOutlined } from "@ant-design/icons";
import { Empty, Input, List, Modal, Spin, Tag, Typography } from "antd";
import { useEffect, useRef, useState } from "react";

import type { DocumentSearchHit } from "../../api/search";
import { searchNovelDocuments } from "../../api/search";

type NovelSearchModalProps = {
  novelId: string;
  onClose: () => void;
  onSelectHit: (hit: DocumentSearchHit) => void;
  open: boolean;
  token: string;
};

export function NovelSearchModal({ novelId, onClose, onSelectHit, open, token }: NovelSearchModalProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<DocumentSearchHit[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestIdRef = useRef(0);

  useEffect(() => {
    if (!open) {
      setQuery("");
      setResults([]);
      setError(null);
      setLoading(false);
      return;
    }
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }

    const trimmed = query.trim();
    if (!trimmed) {
      setResults([]);
      setError(null);
      setLoading(false);
      return;
    }

    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    setLoading(true);
    setError(null);

    const timer = window.setTimeout(() => {
      void searchNovelDocuments(token, novelId, trimmed)
        .then((hits) => {
          if (requestIdRef.current !== requestId) {
            return;
          }
          setResults(hits);
        })
        .catch((searchError: Error) => {
          if (requestIdRef.current !== requestId) {
            return;
          }
          setResults([]);
          setError(searchError.message);
        })
        .finally(() => {
          if (requestIdRef.current === requestId) {
            setLoading(false);
          }
        });
    }, 250);

    return () => {
      window.clearTimeout(timer);
    };
  }, [novelId, open, query, token]);

  return (
    <Modal
      destroyOnHidden
      footer={null}
      onCancel={onClose}
      open={open}
      title="全小说搜索"
      width={720}
    >
      <Input
        allowClear
        autoFocus
        data-testid="novel-search-input"
        onChange={(event) => setQuery(event.target.value)}
        placeholder="搜索章节标题或正文内容"
        prefix={<SearchOutlined />}
        value={query}
      />
      <div data-testid="novel-search-results" style={{ marginTop: 16, minHeight: 180 }}>
        {!query.trim() ? (
          <Typography.Paragraph style={{ marginBottom: 0, marginTop: 24 }} type="secondary">
            输入关键词，将在当前小说的所有章节中搜索。
          </Typography.Paragraph>
        ) : loading ? (
          <div style={{ padding: "48px 0", textAlign: "center" }}>
            <Spin />
          </div>
        ) : error ? (
          <Typography.Paragraph style={{ marginBottom: 0, marginTop: 24 }} type="danger">
            {error}
          </Typography.Paragraph>
        ) : results.length === 0 ? (
          <Empty description="未找到匹配内容" image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ marginTop: 24 }} />
        ) : (
          <List
            dataSource={results}
            renderItem={(hit) => (
              <List.Item
                actions={[
                  <Typography.Link
                    data-testid={`novel-search-open-${hit.document_id}-${hit.match_index}`}
                    key="open"
                    onClick={() => onSelectHit(hit)}
                  >
                    定位
                  </Typography.Link>,
                ]}
              >
                <List.Item.Meta
                  avatar={<FileTextOutlined style={{ color: "#ea580c", fontSize: 18 }} />}
                  description={
                    <Typography.Paragraph ellipsis={{ rows: 2 }} style={{ marginBottom: 0 }} type="secondary">
                      {hit.snippet}
                    </Typography.Paragraph>
                  }
                  title={
                    <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 8 }}>
                      <Typography.Text strong>{hit.node_title}</Typography.Text>
                      {hit.match_source === "title" ? <Tag color="gold">标题匹配</Tag> : null}
                      {hit.match_source === "body" && hit.total_matches_in_document > 1 ? (
                        <Tag color="blue">
                          第 {(hit.occurrence_index ?? 0) + 1} / {hit.total_matches_in_document} 处
                        </Tag>
                      ) : null}
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </div>
    </Modal>
  );
}
