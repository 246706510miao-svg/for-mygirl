import { Pressable } from "../ui/Pressable";
import { fieldLabels, type FieldKey } from "./recordFields";

interface FieldSelectorProps {
  selected: FieldKey[];
  onChange: (value: FieldKey[]) => void;
}

const choices = Object.keys(fieldLabels) as FieldKey[];

// 这个组件控制最近记录显示字段，至少保留一个字段。
export function FieldSelector({ selected, onChange }: FieldSelectorProps) {
  function toggleField(field: FieldKey) {
    const checked = selected.includes(field);
    const next = checked ? selected.filter((item) => item !== field) : [...selected, field];
    if (next.length === 0) {
      return;
    }
    onChange(choices.filter((item) => next.includes(item)));
  }

  return (
    <div className="field-selector" aria-label="记录字段">
      {choices.map((field) => {
        const checked = selected.includes(field);
        return (
          <Pressable
            key={field}
            className={`field-pill${checked ? " is-selected" : ""}`}
            aria-pressed={checked}
            onClick={() => toggleField(field)}
          >
            {fieldLabels[field]}
          </Pressable>
        );
      })}
    </div>
  );
}
