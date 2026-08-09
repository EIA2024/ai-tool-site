import { useState } from "react";
import { invokeTool } from "../../lib/api";

export default function BlankToolPage() {
  const [input, setInput] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    setLoading(true);
    try {
      const res = await invokeTool<{ echo: string; message: string }>(
        "blank_tool",
        { input }
      );
      if (res.success && res.data) {
        setResult(JSON.stringify(res.data, null, 2));
      } else {
        setResult(`Error: ${res.error?.message ?? "Unknown error"}`);
      }
    } catch (err) {
      setResult(`Request failed: ${String(err)}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="tool-page">
      <h2>Blank Tool</h2>
      <p>A request-response tool template. Submit text to see the backend echo it.</p>
      <div className="input-area">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Enter some text..."
        />
        <button onClick={handleSubmit} disabled={loading}>
          {loading ? "Processing..." : "Submit"}
        </button>
      </div>
      {result && (
        <pre className="result-box">
          {result}
        </pre>
      )}
    </div>
  );
}
