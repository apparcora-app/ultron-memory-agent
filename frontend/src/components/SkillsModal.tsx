import React, { useState, useEffect } from "react";
import {
  Sparkles,
  Plus,
  Search,
  X,
  CheckCircle2,
  Tag,
  Layers,
} from "lucide-react";

interface SkillItem {
  id?: string;
  skill_id?: string;
  name: string;
  description: string;
  category?: string;
  icon?: string;
  tags?: string[];
  instructions?: string;
}

interface SkillsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectSkill?: (skill: SkillItem) => void;
}

export const SkillsModal: React.FC<SkillsModalProps> = ({
  isOpen,
  onClose,
  onSelectSkill,
}) => {
  const [skills, setSkills] = useState<SkillItem[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [selectedCategory, setSelectedCategory] = useState<string>("All");
  const [activeTab, setActiveTab] = useState<"browse" | "create">("browse");

  // Create Skill Form State
  const [formId, setFormId] = useState("");
  const [formName, setFormName] = useState("");
  const [formCategory, setFormCategory] = useState("Custom");
  const [formDesc, setFormDesc] = useState("");
  const [formInstructions, setFormInstructions] = useState("");
  const [formTags, setFormTags] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null);

  const fetchSkills = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/skills?user_id=boss");
      if (res.ok) {
        const data = await res.json();
        if (data.skills && Array.isArray(data.skills)) {
          setSkills(data.skills);
        }
      }
    } catch (err) {
      console.error("Failed to load skills:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchSkills();
      setSubmitSuccess(null);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const categories = [
    "All",
    ...Array.from(new Set(skills.map((s) => s.category || "General"))),
  ];

  const filteredSkills = skills.filter((skill) => {
    const matchesSearch =
      (skill.name || "").toLowerCase().includes(searchTerm.toLowerCase()) ||
      (skill.description || "").toLowerCase().includes(searchTerm.toLowerCase()) ||
      (skill.id || skill.skill_id || "").toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory =
      selectedCategory === "All" || (skill.category || "General") === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  const handleCreateSkill = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formId || !formName || !formInstructions) return;

    setSubmitting(true);
    setSubmitSuccess(null);

    try {
      const formData = new FormData();
      formData.append("skill_id", formId.trim().toLowerCase().replace(/\s+/g, "_"));
      formData.append("name", formName.trim());
      formData.append("category", formCategory);
      formData.append("description", formDesc.trim());
      formData.append("instructions", formInstructions.trim());
      formData.append("tags", formTags.trim() || "custom");
      formData.append("user_id", "boss");

      const res = await fetch("/api/skills", {
        method: "POST",
        body: formData,
      });

      if (res.ok) {
        setSubmitSuccess(`Skill "${formName}" successfully integrated into Ultron Matrix!`);
        setFormId("");
        setFormName("");
        setFormDesc("");
        setFormInstructions("");
        setFormTags("");
        fetchSkills();
        setTimeout(() => setActiveTab("browse"), 1500);
      } else {
        const err = await res.json();
        alert(`Failed to install skill: ${err.detail || "Server error"}`);
      }
    } catch (err) {
      alert(`Network error creating skill: ${err}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative w-full max-w-4xl max-h-[85vh] flex flex-col rounded-3xl bg-[#141820] border border-white/10 shadow-[0_20px_60px_rgba(0,0,0,0.8)] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-[#12151c]/90">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 shadow-[0_0_12px_rgba(0,240,255,0.25)]">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-white tracking-wide flex items-center gap-2">
                <span>Ultron Skills Matrix</span>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-cyan-950 text-cyan-400 border border-cyan-800">
                  {skills.length} Loaded
                </span>
              </h2>
              <p className="text-xs text-zinc-400">
                Browse autonomous capabilities, dynamic tools, and install custom execution behaviors
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Tabs */}
            <div className="flex p-1 rounded-xl bg-zinc-900 border border-white/5 text-xs font-medium">
              <button
                onClick={() => setActiveTab("browse")}
                className={`px-3 py-1.5 rounded-lg transition-all ${
                  activeTab === "browse"
                    ? "bg-cyan-500/20 text-cyan-300 font-semibold"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                Browse Matrix
              </button>
              <button
                onClick={() => setActiveTab("create")}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all ${
                  activeTab === "create"
                    ? "bg-cyan-500/20 text-cyan-300 font-semibold"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Skill</span>
              </button>
            </div>

            {/* Close Button */}
            <button
              onClick={onClose}
              className="p-2 rounded-xl text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
              title="Close Modal"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto p-6">
          {activeTab === "browse" ? (
            <div className="space-y-5">
              {/* Search & Category Filter Bar */}
              <div className="flex flex-col sm:flex-row items-center gap-3">
                <div className="relative flex-1 w-full">
                  <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
                  <input
                    type="text"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    placeholder="Search by skill name, capability, or keywords..."
                    className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-[#1a1f2c] border border-white/10 text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:border-cyan-500/60"
                  />
                </div>

                {/* Categories */}
                <div className="flex items-center gap-1.5 overflow-x-auto w-full sm:w-auto pb-1 sm:pb-0">
                  {categories.map((cat) => (
                    <button
                      key={cat}
                      onClick={() => setSelectedCategory(cat)}
                      className={`px-3 py-1.5 rounded-xl text-xs whitespace-nowrap transition-all ${
                        selectedCategory === cat
                          ? "bg-cyan-500 text-zinc-950 font-bold shadow-[0_0_10px_rgba(0,240,255,0.3)]"
                          : "bg-zinc-900/80 border border-white/5 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800"
                      }`}
                    >
                      {cat}
                    </button>
                  ))}
                </div>
              </div>

              {/* Skills Grid */}
              {loading ? (
                <div className="flex flex-col items-center justify-center py-16 text-zinc-400 gap-3">
                  <div className="w-8 h-8 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
                  <span className="text-xs font-mono">Synchronizing Skills Matrix...</span>
                </div>
              ) : filteredSkills.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-zinc-500 gap-2 border border-dashed border-white/10 rounded-2xl">
                  <Layers className="w-8 h-8 text-zinc-600" />
                  <p className="text-sm">No skills found matching your query.</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                  {filteredSkills.map((skill, idx) => {
                    const skillId = skill.id || skill.skill_id || `skill-${idx}`;
                    return (
                      <div
                        key={skillId}
                        className="group relative flex flex-col justify-between p-4 rounded-2xl bg-[#191e28] border border-white/5 hover:border-cyan-500/40 hover:bg-[#1d2330] transition-all shadow-sm"
                      >
                        <div>
                          <div className="flex items-start justify-between gap-2 mb-2">
                            <div className="flex items-center gap-2.5">
                              <span className="text-xl">{skill.icon || "⚡"}</span>
                              <div>
                                <h3 className="text-sm font-semibold text-zinc-100 group-hover:text-cyan-300 transition-colors">
                                  {skill.name}
                                </h3>
                                <span className="text-[10px] font-mono text-zinc-500">
                                  {skillId}
                                </span>
                              </div>
                            </div>
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-zinc-800/80 text-zinc-400 border border-white/5">
                              {skill.category || "General"}
                            </span>
                          </div>

                          <p className="text-xs text-zinc-400 leading-relaxed line-clamp-3 mb-3">
                            {skill.description || "No description provided."}
                          </p>
                        </div>

                        {/* Tags & Action */}
                        <div className="flex items-center justify-between pt-2 border-t border-white/5">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            {skill.tags &&
                              skill.tags.slice(0, 3).map((tag, tIdx) => (
                                <span
                                  key={tIdx}
                                  className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded text-[10px] bg-zinc-800 text-zinc-400 font-mono"
                                >
                                  <Tag className="w-2.5 h-2.5 text-cyan-400" />
                                  {tag}
                                </span>
                              ))}
                          </div>

                          {onSelectSkill && (
                            <button
                              onClick={() => {
                                onSelectSkill(skill);
                                onClose();
                              }}
                              className="px-3 py-1 rounded-lg text-xs font-medium bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 hover:bg-cyan-500 hover:text-zinc-950 transition-all"
                            >
                              Activate
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          ) : (
            /* Create Skill Form */
            <form onSubmit={handleCreateSkill} className="space-y-4 max-w-2xl mx-auto">
              {submitSuccess && (
                <div className="flex items-center gap-2 p-3.5 rounded-xl bg-emerald-950/80 border border-emerald-500/50 text-emerald-300 text-xs">
                  <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
                  <span>{submitSuccess}</span>
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-zinc-300 mb-1">
                    Skill Identifier (ID) *
                  </label>
                  <input
                    type="text"
                    required
                    value={formId}
                    onChange={(e) => setFormId(e.target.value)}
                    placeholder="e.g. data_visualizer"
                    className="w-full px-3.5 py-2 rounded-xl bg-[#1a1f2c] border border-white/10 text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:border-cyan-500/60 font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-zinc-300 mb-1">
                    Display Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={formName}
                    onChange={(e) => setFormName(e.target.value)}
                    placeholder="e.g. Advanced Data Visualizer"
                    className="w-full px-3.5 py-2 rounded-xl bg-[#1a1f2c] border border-white/10 text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:border-cyan-500/60"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-zinc-300 mb-1">
                    Category
                  </label>
                  <select
                    value={formCategory}
                    onChange={(e) => setFormCategory(e.target.value)}
                    className="w-full px-3.5 py-2 rounded-xl bg-[#1a1f2c] border border-white/10 text-sm text-zinc-200 focus:outline-none focus:border-cyan-500/60"
                  >
                    <option value="Custom">Custom</option>
                    <option value="Development">Development</option>
                    <option value="Media">Media & Creative</option>
                    <option value="Analysis">Analysis & Data</option>
                    <option value="Security">Security & Verification</option>
                    <option value="Financial">Financial & Ledger</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-zinc-300 mb-1">
                    Tags (Comma-separated)
                  </label>
                  <input
                    type="text"
                    value={formTags}
                    onChange={(e) => setFormTags(e.target.value)}
                    placeholder="e.g. chart, plotting, matplotlib"
                    className="w-full px-3.5 py-2 rounded-xl bg-[#1a1f2c] border border-white/10 text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:border-cyan-500/60 font-mono text-xs"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-300 mb-1">
                  Brief Summary / Description
                </label>
                <input
                  type="text"
                  value={formDesc}
                  onChange={(e) => setFormDesc(e.target.value)}
                  placeholder="Summarize what this skill enables Ultron to execute"
                  className="w-full px-3.5 py-2 rounded-xl bg-[#1a1f2c] border border-white/10 text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:border-cyan-500/60"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-300 mb-1">
                  Agent Execution Instructions / Prompt Directive *
                </label>
                <textarea
                  required
                  rows={5}
                  value={formInstructions}
                  onChange={(e) => setFormInstructions(e.target.value)}
                  placeholder="Provide precise guidelines, tool workflows, and output format standards for Ultron when using this skill..."
                  className="w-full px-3.5 py-2 rounded-xl bg-[#1a1f2c] border border-white/10 text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:border-cyan-500/60 font-mono text-xs leading-relaxed"
                />
              </div>

              <div className="flex justify-end pt-3">
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-cyan-500 text-zinc-950 font-bold text-sm hover:bg-cyan-400 transition-all shadow-[0_0_15px_rgba(0,240,255,0.4)] disabled:opacity-50"
                >
                  {submitting ? (
                    <div className="w-4 h-4 border-2 border-zinc-950 border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <Plus className="w-4 h-4" />
                  )}
                  <span>Install Skill into Matrix</span>
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
