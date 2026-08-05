import { useRef, useState } from "react";
import { uploadImport } from "../api";
import { IconCheckCircle, IconSpinner, IconUpload } from "./icons";
import type { IngestUploadResult } from "../types";

interface Props {
  /** "onboarding" fills the whole screen with no way to dismiss (no data
   * loaded yet); "modal" is a dismissable overlay for re-importing a
   * fresh export over existing data. */
  variant: "onboarding" | "modal";
  onImported: () => void;
  onClose?: () => void;
}

const COUNT_LABELS: [key: string, label: string][] = [
  ["timetable_entry", "timetable entries"],
  ["student", "students"],
  ["teacher", "teachers"],
  ["room", "rooms"],
  ["sfx_file", "student options files"],
];

export default function ImportPanel({ variant, onImported, onClose }: Props) {
  const [tfxFile, setTfxFile] = useState<File | null>(null);
  const [sfxFiles, setSfxFiles] = useState<File[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<IngestUploadResult | null>(null);
  const tfxInputRef = useRef<HTMLInputElement>(null);
  const sfxInputRef = useRef<HTMLInputElement>(null);

  const reset = () => {
    setTfxFile(null);
    setSfxFiles([]);
    setError(null);
    setResult(null);
    if (tfxInputRef.current) tfxInputRef.current.value = "";
    if (sfxInputRef.current) sfxInputRef.current.value = "";
  };

  const handleSubmit = async () => {
    if (!tfxFile) return;
    setSubmitting(true);
    setError(null);
    try {
      const uploadResult = await uploadImport(tfxFile, sfxFiles);
      setResult(uploadResult);
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  };

  const handleContinue = () => {
    onImported();
    reset();
  };

  const body = (
    <div className={variant === "onboarding" ? "mx-auto max-w-xl" : ""}>
      {variant === "onboarding" && (
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-sky-50 text-sky-600">
            <IconUpload className="h-6 w-6" />
          </div>
          <h1 className="text-lg font-semibold text-slate-900">Load a timetable to get started</h1>
          <p className="mt-1 text-sm text-slate-500">
            Choose the <code className="rounded bg-slate-100 px-1 py-0.5">.tfx</code> export from Timetabling
            Solutions. Student Options (<code className="rounded bg-slate-100 px-1 py-0.5">.sfx</code>) files are
            optional and can be added later.
          </p>
        </div>
      )}

      {!result && (
        <div className="flex flex-col gap-4 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <FilePickerField
            inputRef={tfxInputRef}
            label="Timetable file"
            required
            accept=".tfx"
            multiple={false}
            files={tfxFile ? [tfxFile] : []}
            placeholder="Choose a .tfx file…"
            onChange={(files) => setTfxFile(files[0] ?? null)}
          />
          <FilePickerField
            inputRef={sfxInputRef}
            label="Student options files (optional)"
            accept=".sfx"
            multiple
            files={sfxFiles}
            placeholder="Choose one or more .sfx files…"
            onChange={setSfxFiles}
          />

          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
          )}

          <div className="flex items-center justify-between gap-3">
            {variant === "modal" && (
              <button type="button" onClick={onClose} className="text-sm text-slate-500 hover:text-slate-700">
                Cancel
              </button>
            )}
            <button
              type="button"
              disabled={!tfxFile || submitting}
              onClick={handleSubmit}
              className="ml-auto flex items-center gap-2 rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white transition-colors duration-150 hover:bg-sky-700 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              {submitting && <IconSpinner className="h-4 w-4" />}
              {submitting ? "Importing…" : "Import"}
            </button>
          </div>
        </div>
      )}

      {result && <ImportSummary result={result} onContinue={handleContinue} />}
    </div>
  );

  if (variant === "onboarding") {
    return <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6 py-12">{body}</div>;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-slate-900/40 px-6 py-16">
      <div className="w-full max-w-xl">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-base font-semibold text-white">Import a timetable</h2>
          {!submitting && (
            <button type="button" onClick={onClose} className="text-sm text-slate-200 hover:text-white">
              ✕ Close
            </button>
          )}
        </div>
        {body}
      </div>
    </div>
  );
}

function FilePickerField({
  inputRef,
  label,
  required,
  accept,
  multiple,
  files,
  placeholder,
  onChange,
}: {
  inputRef: React.RefObject<HTMLInputElement | null>;
  label: string;
  required?: boolean;
  accept: string;
  multiple: boolean;
  files: File[];
  placeholder: string;
  onChange: (files: File[]) => void;
}) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
        {label}
        {required && <span className="ml-1 text-red-500">*</span>}
      </label>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        className="w-full rounded-md border border-dashed border-slate-300 px-3 py-2 text-left text-sm text-slate-600 hover:border-sky-400 hover:bg-sky-50"
      >
        {files.length === 0 ? placeholder : files.map((f) => f.name).join(", ")}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        className="hidden"
        onChange={(e) => onChange(Array.from(e.target.files ?? []))}
      />
    </div>
  );
}

function ImportSummary({ result, onContinue }: { result: IngestUploadResult; onContinue: () => void }) {
  const errors = result.discrepancies.filter((d) => d.severity === "error");
  const warnings = result.discrepancies.filter((d) => d.severity === "warning");

  return (
    <div className="flex flex-col gap-4 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start gap-2">
        <IconCheckCircle className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
        <div>
          <p className="text-sm font-medium text-emerald-700">Import complete - {result.tfx_filename}</p>
          {result.sfx_filenames.length > 0 && (
            <p className="mt-0.5 text-xs text-slate-500">
              Plus {result.sfx_filenames.length} student options file(s): {result.sfx_filenames.join(", ")}
            </p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {COUNT_LABELS.map(([key, label]) => (
          <div key={key} className="rounded-md bg-slate-50 px-3 py-2">
            <div className="text-lg font-semibold text-slate-900">{result.counts[key] ?? 0}</div>
            <div className="text-xs text-slate-500">{label}</div>
          </div>
        ))}
      </div>

      <div className="rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-600">
        Rules engine found <span className="font-medium text-slate-900">{result.analysis.findings_total}</span>{" "}
        finding(s) to review.
      </div>

      {warnings.length > 0 && (
        <details className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          <summary className="cursor-pointer font-medium">
            {warnings.length} note{warnings.length === 1 ? "" : "s"} from cross-checking the source files
          </summary>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {warnings.map((w, i) => (
              <li key={i}>{w.description}</li>
            ))}
          </ul>
        </details>
      )}
      {errors.length > 0 && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          <p className="font-medium">{errors.length} discrepancy needs attention:</p>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            {errors.map((e, i) => (
              <li key={i}>{e.description}</li>
            ))}
          </ul>
        </div>
      )}

      <button
        type="button"
        onClick={onContinue}
        className="rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-700"
      >
        View timetable
      </button>
    </div>
  );
}
