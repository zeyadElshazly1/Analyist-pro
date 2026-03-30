"use client";

import { useState, useRef, useEffect } from "react";
import { sendChatMessage } from "@/lib/api";
import { Loader2, Send, Bot, User, Code2, Table2 } from "lucide-react";
import { Button } from "@/components/ui/button";

type Message = {
  role: "user" | "assistant";
  content: string;
  code?: string | null;
  resultType?: string;
  tableData?: Record<string, unknown>[] | null;
  numberResult?: number | null;
};

type Props = { projectId: number };

export function AiChatView({ projectId }: Props) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: "Hi! I'm your AI data analyst. Ask me anything about your dataset — I can calculate statistics, find patterns, filter data, and more.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend() {
    const msg = input.trim();
    if (!msg || loading) return;
    setInput("");
    const userMsg: Message = { role: "user", content: msg };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const history = messages.map((m) => ({ role: m.role, content: m.content }));
      const res = await sendChatMessage(projectId, msg, history) as any;
      const assistantMsg: Message = {
        role: "assistant",
        content: res.answer || "I couldn't generate a response.",
        code: res.code_used,
        resultType: res.result_type,
        tableData: res.table_data,
        numberResult: res.number_result,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (e: any) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${e.message}` },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="flex flex-col h-[600px]">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <Bot className="h-5 w-5 text-indigo-400" /> Ask AI
        </h2>
        <p className="text-sm text-white/50">Ask questions about your data in plain English.</p>
      </div>

      {/* Message thread */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-1 mb-4">
        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}>
            <div className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center ${msg.role === "user" ? "bg-indigo-600" : "bg-white/[0.08]"}`}>
              {msg.role === "user" ? <User className="h-3.5 w-3.5 text-white" /> : <Bot className="h-3.5 w-3.5 text-indigo-400" />}
            </div>
            <div className={`flex-1 max-w-[85%] space-y-2 ${msg.role === "user" ? "items-end" : "items-start"} flex flex-col`}>
              <div className={`rounded-2xl px-4 py-2.5 text-sm ${msg.role === "user" ? "bg-indigo-600 text-white rounded-tr-sm" : "bg-white/[0.06] text-white/90 rounded-tl-sm"}`}>
                {msg.content}
              </div>

              {/* Number result */}
              {msg.resultType === "number" && msg.numberResult != null && (
                <div className="rounded-lg bg-indigo-500/10 border border-indigo-500/20 px-4 py-2 text-indigo-300 text-lg font-semibold">
                  {msg.numberResult}
                </div>
              )}

              {/* Code block */}
              {msg.code && (
                <div className="w-full rounded-lg bg-[#0f172a] border border-white/10 overflow-hidden">
                  <div className="flex items-center gap-2 px-3 py-1.5 bg-white/[0.04] border-b border-white/10">
                    <Code2 className="h-3.5 w-3.5 text-indigo-400" />
                    <span className="text-xs text-white/50">Generated code</span>
                  </div>
                  <pre className="p-3 text-xs text-green-300 overflow-x-auto whitespace-pre-wrap">{msg.code}</pre>
                </div>
              )}

              {/* Table result */}
              {msg.resultType === "table" && msg.tableData && msg.tableData.length > 0 && (
                <div className="w-full rounded-lg border border-white/[0.07] overflow-hidden">
                  <div className="flex items-center gap-2 px-3 py-1.5 bg-white/[0.04] border-b border-white/10">
                    <Table2 className="h-3.5 w-3.5 text-indigo-400" />
                    <span className="text-xs text-white/50">Result ({msg.tableData.length} rows)</span>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-white/[0.07]">
                          {Object.keys(msg.tableData[0]).map((col) => (
                            <th key={col} className="px-3 py-2 text-left text-white/50 font-medium whitespace-nowrap">{col}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {msg.tableData.slice(0, 10).map((row, ri) => (
                          <tr key={ri} className="border-b border-white/[0.04]">
                            {Object.values(row).map((val, vi) => (
                              <td key={vi} className="px-3 py-2 text-white/70 whitespace-nowrap">{String(val ?? "—")}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex gap-3">
            <div className="w-7 h-7 rounded-full bg-white/[0.08] flex items-center justify-center">
              <Bot className="h-3.5 w-3.5 text-indigo-400" />
            </div>
            <div className="rounded-2xl rounded-tl-sm bg-white/[0.06] px-4 py-3">
              <Loader2 className="h-4 w-4 text-indigo-400 animate-spin" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about your data… (e.g. 'What's the average revenue by region?')"
          className="flex-1 rounded-xl bg-white/[0.05] border border-white/10 px-4 py-2.5 text-sm text-white placeholder:text-white/30 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          disabled={loading}
        />
        <Button
          onClick={handleSend}
          disabled={loading || !input.trim()}
          className="bg-indigo-600 hover:bg-indigo-500 text-white px-4"
        >
          <Send className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
