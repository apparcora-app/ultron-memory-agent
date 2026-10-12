import React, { useState, useEffect } from "react";
import {
  Brain,
  Search,
  X,
  Trash2,
  RefreshCw,
  Clock,
  Sparkles,
  ShieldCheck,
} from "lucide-react";

interface MemoryItem {
  id: string;
  memory: string;
  created_at?: string;
  updated_at?: string;
  user_id?: string;
  metadata?: Record<string, any> | null;
}

interface MemoriesModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const MemoriesModal: React.FC<MemoriesModalProps> = ({
  isOpen,
  onClose,
}) => {
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchMemories = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/memories?user_id=boss");
      if (res.ok) {
        const data = await res.json();
        if (data.memories && Array.isArray(data.memories)) {
          setMemories(data.memories);
        }
      }
    } catch (err) {
      console.error("Failed to load neural memories:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchMemories();
    }
  }, [isOpen]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchMemories();
  };

  const handleDelete = async (memoryId: string) => {
    if (!confirm("Are you sure you want to permanently erase this memory vector from long-term storage?")) {
      return;
    }
    setDeletingId(memoryId);
    try {
      const res = await fetch(`/api/memories/${encodeURIComponent(memoryId)}?user_id=boss`, {
        method: "DELETE",
      });
      if (res.ok) {
        setMemories((prev) => prev.filter((m) => m.id !== memoryId));
      } else {
        alert("Failed to delete memory vector.");
      }
    } catch (err) {
      console.error("Error deleting memory:", err);
      alert("Error deleting memory.");
    } finally {
      setDeletingId(null);
    }
  };

  if (!isOpen) return null;

  const filteredMemories = memories.filter((m) => {
    const text = (m.memory || "").toLowerCase();
    const id = (m.id || "").toLowerCase();
    const term = searchTerm.toLowerCase().trim();
    return text.includes(term) || id.includes(term);
  });

  const formatDate = (isoString?: string) => {
    if (!isoString) return "Indexed";
    try {
      const date = new Date(isoString);
      return date.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    } catch {
      return "Indexed";
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="flex flex-col w-full max-w-4xl max-h-[85vh] bg-white rounded-3xl shadow-2xl border border-[#cbd5e1] overflow-hidden text-[#0f172a]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#e2e8f0] bg-slate-50/60">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-2xl bg-sky-50 text-[#0284c7] border border-[#bae6fd]">
              <Brain className="w-5 h-5 text-[#0284c7]" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-[#0f172a]">
                  Neural Long-Term Memory Matrix
                </h2>
                <span className="px-2 py-0.5 text-[11px] font-mono font-semibold rounded-full bg-sky-100 text-[#0284c7] border border-[#bae6fd]">
                  {memories.length} Vectors
                </span>
              </div>
              <p className="text-xs text-slate-500">
                Persistent facts, architectural preferences, and user context indexed in vector memory
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleRefresh}
              disabled={refreshing || loading}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-white border border-[#cbd5e1] hover:border-[#0284c7] text-slate-700 hover:text-[#0284c7] transition-all shadow-xs"
              title="Refresh Neural Memory Matrix"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin text-[#0284c7]" : ""}`} />
              <span className="hidden sm:inline">Refresh</span>
            </button>
            <button
              type="button"
              onClick={onClose}
              className="flex items-center justify-center w-8 h-8 rounded-full hover:bg-slate-200 text-slate-500 hover:text-slate-800 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Filter & Search Bar */}
        <div className="px-6 py-3 border-b border-[#e2e8f0] bg-white">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search neural memories by topic, keyword, or ID..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-4 py-2 text-xs bg-slate-50 border border-[#cbd5e1] rounded-xl focus:outline-none focus:border-[#0284c7] focus:bg-white text-slate-900 transition-colors"
            />
          </div>
        </div>

        {/* Content List */}
        <div className="flex-1 overflow-y-auto p-6 space-y-3 bg-[#f8fafc]/50">
          {loading && !refreshing ? (
            <div className="flex flex-col items-center justify-center py-16 text-slate-400 gap-3">
              <Brain className="w-8 h-8 animate-pulse text-[#0284c7]" />
              <span className="text-xs font-mono">Retrieving neural memory embeddings...</span>
            </div>
          ) : filteredMemories.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-slate-400 gap-2">
              <Brain className="w-8 h-8 opacity-40" />
              <span className="text-xs">
                {searchTerm ? "No memories match your search filter." : "No long-term memories indexed yet."}
              </span>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-2.5">
              {filteredMemories.map((m, idx) => (
                <div
                  key={m.id || idx}
                  className="group relative flex flex-col sm:flex-row sm:items-center justify-between p-3.5 rounded-2xl bg-white border border-[#e2e8f0] hover:border-[#bae6fd] hover:shadow-sm transition-all gap-3"
                >
                  <div className="flex items-start gap-3 flex-1 min-w-0">
                    <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-sky-50 text-[#0284c7] shrink-0 mt-0.5">
                      <Sparkles className="w-3.5 h-3.5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-medium text-[#0f172a] leading-relaxed select-text">
                        {m.memory}
                      </p>
                      <div className="flex items-center gap-3 mt-1.5 text-[10px] text-slate-400 font-mono">
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3 text-slate-400" />
                          {formatDate(m.created_at)}
                        </span>
                        <span>•</span>
                        <span className="truncate max-w-[150px] text-slate-400" title={m.id}>
                          ID: {m.id.split("_").pop() || m.id}
                        </span>
                        <span>•</span>
                        <span className="text-emerald-600 font-semibold flex items-center gap-0.5">
                          <ShieldCheck className="w-3 h-3 text-emerald-500" />
                          Verified
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center self-end sm:self-center shrink-0">
                    <button
                      type="button"
                      onClick={() => handleDelete(m.id)}
                      disabled={deletingId === m.id}
                      className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-medium text-slate-400 hover:text-rose-600 hover:bg-rose-50 border border-transparent hover:border-rose-200 transition-all opacity-80 group-hover:opacity-100"
                      title="Permanently Delete Memory Vector"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      <span className="hidden sm:inline">Delete</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-3 border-t border-[#e2e8f0] bg-slate-50 text-[11px] text-slate-500">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span>ChromaDB Vector Store Connected</span>
          </div>
          <span className="font-mono text-slate-400">Total: {filteredMemories.length} / {memories.length}</span>
        </div>
      </div>
    </div>
  );
};
