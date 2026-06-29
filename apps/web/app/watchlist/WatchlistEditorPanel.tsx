"use client";

import { Button, Card, Form, Input, Typography } from "antd";
import type { DraftItem } from "./types";

export type WatchlistEditorPanelProps = {
  draft: DraftItem;
  onDraftChange: (draft: DraftItem) => void;
  onSave: () => void;
  saving: boolean;
  selected: boolean;
};

export function WatchlistEditorPanel({
  draft,
  onDraftChange,
  onSave,
  saving,
  selected,
}: WatchlistEditorPanelProps) {
  return (
    <Card
      className="workbench-panel xl:sticky xl:top-4 xl:max-h-[calc(100vh-2rem)] xl:overflow-y-auto"
      styles={{ body: { padding: 0 } }}
    >
      <div className="workbench-panel-divider border-b px-5 py-4">
        <Typography.Text className="workbench-muted text-xs font-semibold uppercase">Edit</Typography.Text>
        <Typography.Title className="workbench-ink mt-1 text-xl font-black" level={2}>
          {selected ? "编辑自选股" : "新增自选股"}
        </Typography.Title>
      </div>
      <Form className="p-5" layout="vertical">
        <EditorInput label="股票代码" onChange={(value) => onDraftChange({ ...draft, symbol: value })} value={draft.symbol} />
        <EditorInput label="名称" onChange={(value) => onDraftChange({ ...draft, name: value })} value={draft.name} />
        <EditorInput label="分组" onChange={(value) => onDraftChange({ ...draft, group: value })} value={draft.group} />
        <EditorInput label="行业" onChange={(value) => onDraftChange({ ...draft, industry: value })} value={draft.industry} />
        <EditorInput label="标签" onChange={(value) => onDraftChange({ ...draft, tagsText: value })} value={draft.tagsText} />
        <Form.Item label="备注">
          <Input.TextArea
            autoSize={{ minRows: 4, maxRows: 8 }}
            onChange={(event) => onDraftChange({ ...draft, note: event.target.value })}
            placeholder="记录买入观察理由、关键均线、风险点"
            value={draft.note}
          />
        </Form.Item>
        <Button block disabled={saving} loading={saving} onClick={onSave} type="primary">
          保存
        </Button>
      </Form>
    </Card>
  );
}

function EditorInput({
  label,
  onChange,
  value,
}: {
  label: string;
  onChange: (value: string) => void;
  value: string;
}) {
  return (
    <Form.Item label={label}>
      <Input onChange={(event) => onChange(event.target.value)} value={value} />
    </Form.Item>
  );
}
