"use client";

import { useMemo, useState } from "react";
import type { MemoryDomainTemplateItem, MemoryEntityCreateResponse } from "@/types/memory";
import { createMemoryEntityFromTemplate, queueMemoryEntityDomainReviewQuestions } from "@/lib/api-client";

export default function MemoryTemplateCreator({
  templates,
  onCreated,
}: {
  templates: MemoryDomainTemplateItem[];
  onCreated: (result: MemoryEntityCreateResponse) => void | Promise<void>;
}) {
  const [selectedTemplateId, setSelectedTemplateId] = useState("product");
  const [label, setLabel] = useState("");
  const [notes, setNotes] = useState("");
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({});
  const [status, setStatus] = useState("");

  const selectedTemplate = useMemo(
    () => templates.find((template) => template.template_id === selectedTemplateId) || templates[0],
    [templates, selectedTemplateId]
  );
  const fields = Object.entries(selectedTemplate?.fields || {});

  async function handleCreate() {
    if (!selectedTemplate || !label.trim()) {
      setStatus("Choose a template and name the memory.");
      return;
    }
    setStatus("");
    const attributes = Object.fromEntries(
      Object.entries(fieldValues).filter(([, value]) => value.trim())
    );
    const created = await createMemoryEntityFromTemplate(selectedTemplate.template_id, {
      label,
      attributes,
      notes: notes || null,
      lifecycle_state: "candidate",
    });
    await queueMemoryEntityDomainReviewQuestions(created.entity.entity_id);
    setLabel("");
    setNotes("");
    setFieldValues({});
    setStatus(`Created ${created.entity.label} and queued review questions.`);
    await onCreated(created);
  }

  return (
    <div className="card p-5 space-y-4 lg:col-span-1">
      <div>
        <p className="text-xs uppercase tracking-wide text-gray-400">Template Creator</p>
        <h2 className="text-xl font-semibold">New Memory</h2>
      </div>

      <label className="block space-y-2 text-sm">
        <span className="text-gray-300">Type</span>
        <select
          value={selectedTemplateId}
          onChange={(event) => {
            setSelectedTemplateId(event.target.value);
            setFieldValues({});
          }}
          className="w-full rounded-md border border-white/10 bg-black/30 px-3 py-2 text-gray-100"
        >
          {templates.map((template) => (
            <option key={template.template_id} value={template.template_id}>
              {template.display_name}
            </option>
          ))}
        </select>
      </label>

      <label className="block space-y-2 text-sm">
        <span className="text-gray-300">Name</span>
        <input
          value={label}
          onChange={(event) => setLabel(event.target.value)}
          className="w-full rounded-md border border-white/10 bg-black/30 px-3 py-2 text-gray-100"
          placeholder="Camera Lens"
        />
      </label>

      {fields.slice(0, 5).map(([fieldName, fieldType]) => (
        <label key={fieldName} className="block space-y-2 text-sm">
          <span className="text-gray-300">
            {fieldName.replaceAll("_", " ")} <span className="text-gray-500">({fieldType})</span>
          </span>
          <input
            value={fieldValues[fieldName] || ""}
            onChange={(event) =>
              setFieldValues((current) => ({ ...current, [fieldName]: event.target.value }))
            }
            className="w-full rounded-md border border-white/10 bg-black/30 px-3 py-2 text-gray-100"
          />
        </label>
      ))}

      <label className="block space-y-2 text-sm">
        <span className="text-gray-300">Notes</span>
        <textarea
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          className="min-h-24 w-full rounded-md border border-white/10 bg-black/30 px-3 py-2 text-gray-100"
        />
      </label>

      <button
        type="button"
        onClick={() => void handleCreate()}
        className="w-full rounded-md bg-board-accent px-4 py-2 font-semibold text-black"
      >
        Create Memory
      </button>
      {status && <p className="text-sm text-emerald-300">{status}</p>}
    </div>
  );
}
