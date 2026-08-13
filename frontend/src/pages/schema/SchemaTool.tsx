import { useState, type FormEvent } from "react";
import type {
  JsonSchema,
  OperationManifest,
  ToolClient,
  ToolPluginProps,
} from "../../types";

/**
 * Generic schema-driven tool page. Renders every request-response operation as
 * a form generated from its `input_schema`, then displays the `output_schema`
 * result as pretty JSON. Blank Tool and any future schema-only plugin render
 * here with no custom frontend entry.
 */
export default function SchemaTool({ client, manifest }: ToolPluginProps) {
  const operations = manifest.operations.filter(
    (op) => op.transport === "request-response"
  );

  return (
    <div className="tool-page schema-tool">
      <h2>{manifest.name}</h2>
      <p>{manifest.description}</p>
      {operations.map((op) => (
        <OperationCard key={op.id} client={client} operation={op} />
      ))}
    </div>
  );
}

function OperationCard({
  client,
  operation,
}: {
  client: ToolClient;
  operation: OperationManifest;
}) {
  const [result, setResult] = useState<unknown>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const run = async (values: Record<string, unknown>) => {
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const res = await client.invoke(operation.id, values);
      if (res.success) {
        setResult(res.data);
      } else {
        setError(res.error?.message ?? "Operation failed");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="schema-operation">
      <h3>{operation.id}</h3>
      <SchemaForm schema={operation.input_schema} onSubmit={run} submitting={submitting} />
      {error && <div className="schema-error">{error}</div>}
      {result !== null && <SchemaResult value={result} />}
    </section>
  );
}

type FieldKind = "boolean" | "number" | "array" | "enum" | "string";

function fieldKind(schema: JsonSchema): FieldKind {
  if (schema.type === "boolean") return "boolean";
  if (schema.type === "integer" || schema.type === "number") return "number";
  if (schema.type === "array") return "array";
  if (schema.enum || schema.anyOf) return "enum";
  return "string";
}

function coerceValue(schema: JsonSchema, raw: string): unknown {
  switch (fieldKind(schema)) {
    case "boolean":
      return raw === "true";
    case "number":
      return Number(raw);
    case "array":
      return parseList(raw);
    default:
      return raw;
  }
}

function parseList(raw: string): string[] {
  const trimmed = raw.trim();
  if (!trimmed) return [];
  try {
    const parsed = JSON.parse(trimmed);
    if (Array.isArray(parsed)) return parsed.map(String);
  } catch {
    /* fall through to line/comma split */
  }
  return trimmed
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function enumOptions(schema: JsonSchema): string[] {
  if (Array.isArray(schema.enum)) return schema.enum.map(String);
  if (Array.isArray(schema.anyOf)) {
    const options: string[] = [];
    for (const branch of schema.anyOf) {
      if (typeof branch === "object" && branch && "const" in branch) {
        options.push(String(branch.const));
      }
    }
    if (options.length) return options;
  }
  return [];
}

function initialValue(schema: JsonSchema): string {
  if (fieldKind(schema) === "boolean") return schema.default ? "true" : "false";
  if (schema.default === undefined || schema.default === null) return "";
  return String(schema.default);
}

export function SchemaForm({
  schema,
  onSubmit,
  submitting = false,
}: {
  schema: JsonSchema;
  onSubmit: (values: Record<string, unknown>) => void;
  submitting?: boolean;
}) {
  const properties = schema.properties ?? {};
  const required = new Set(schema.required ?? []);
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      Object.entries(properties).map(([key, prop]) => [key, initialValue(prop)])
    )
  );

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const coerced: Record<string, unknown> = {};
    for (const [key, prop] of Object.entries(properties)) {
      const raw = values[key] ?? "";
      const kind = fieldKind(prop);
      if (required.has(key) && raw === "") return;
      if (
        kind === "string" &&
        ((prop.minLength !== undefined && raw.length < prop.minLength) ||
          (prop.maxLength !== undefined && raw.length > prop.maxLength))
      ) {
        return;
      }
      if (kind === "number") {
        if (raw === "") continue;
        const value = Number(raw);
        if (
          !Number.isFinite(value) ||
          (prop.minimum !== undefined && value < prop.minimum) ||
          (prop.maximum !== undefined && value > prop.maximum)
        ) {
          return;
        }
      }
      coerced[key] = coerceValue(prop, raw);
    }
    onSubmit(coerced);
  };

  return (
    <form className="schema-form" onSubmit={handleSubmit}>
      {Object.entries(properties).map(([name, prop]) => (
        <Field
          key={name}
          name={name}
          schema={prop}
          required={required.has(name)}
          value={values[name] ?? ""}
          onChange={(value) => setValues((prev) => ({ ...prev, [name]: value }))}
        />
      ))}
      <button type="submit" disabled={submitting}>
        {submitting ? "Running…" : "Run"}
      </button>
    </form>
  );
}

function Field({
  name,
  schema,
  required,
  value,
  onChange,
}: {
  name: string;
  schema: JsonSchema;
  required: boolean;
  value: string;
  onChange: (value: string) => void;
}) {
  const label = schema.title ?? name;
  const kind = fieldKind(schema);
  const id = `schema-${name}`;

  if (kind === "boolean") {
    return (
      <label className="schema-field schema-field-boolean" htmlFor={id}>
        <input
          id={id}
          type="checkbox"
          checked={value === "true"}
          onChange={(e) => onChange(e.target.checked ? "true" : "false")}
        />
        {label}
      </label>
    );
  }

  if (kind === "enum") {
    const options = enumOptions(schema);
    return (
      <label className="schema-field" htmlFor={id}>
        <span>
          {label}
          {required ? " *" : ""}
        </span>
        <select
          id={id}
          value={value}
          required={required}
          onChange={(e) => onChange(e.target.value)}
        >
          {value === "" && <option value="" />}
          {options.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </label>
    );
  }

  if (kind === "array") {
    return (
      <label className="schema-field" htmlFor={id}>
        <span>
          {label}
          {required ? " *" : ""}
        </span>
        <textarea
          id={id}
          value={value}
          required={required}
          placeholder="JSON array or one item per line"
          onChange={(e) => onChange(e.target.value)}
        />
      </label>
    );
  }

  return (
    <label className="schema-field" htmlFor={id}>
      <span>
        {label}
        {required ? " *" : ""}
      </span>
      <input
        id={id}
        type={kind === "number" ? "number" : "text"}
        value={value}
        required={required}
        minLength={kind === "string" ? schema.minLength : undefined}
        maxLength={kind === "string" ? schema.maxLength : undefined}
        min={kind === "number" ? schema.minimum : undefined}
        max={kind === "number" ? schema.maximum : undefined}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}

function SchemaResult({ value }: { value: unknown }) {
  return <pre className="schema-result">{JSON.stringify(value, null, 2)}</pre>;
}
