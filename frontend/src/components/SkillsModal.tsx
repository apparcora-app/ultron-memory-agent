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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-4xl max-h-[85vh] flex flex-col rounded-3xl bg-white border border-[#cbd5e1] shadow-2xl overflow-hidden text-[#0f172a]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#e2e8f0] bg-[#f8fafc]">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-[#f0f9ff] border border-[#bae6fd] text-[#0284c7] shadow-sm">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-[#0f172a] tracking-wide flex items-center gap-2">
                <span>Ultron Skills Matrix</span>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-sky-50 text-[#0284c7] border border-sky-200 font-semibold">
                  {skills.length} Loaded
                </span>
              </h2>
              <p className="text-xs text-slate-500">
                Browse autonomous capabilities, dynamic tools, and install custom execution behaviors
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Tabs */}
            <div className="flex p-1 rounded-xl bg-[#f1f5f9] border border-[#e2e8f0] text-xs font-medium">
              <button
                onClick={() => setActiveTab("browse")}
                className={`px-3 py-1.5 rounded-lg transition-all ${
                  activeTab === "browse"
                    ? "bg-white text-[#0284c7] font-semibold shadow-xs"
                    : "text-slate-600 hover:text-[#0f172a]"
                }`}
              >
                Browse Matrix
              </button>
              <button
                onClick={() => setActiveTab("create")}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all ${
                  activeTab === "create"
                    ? "bg-white text-[#0284c7] font-semibold shadow-xs"
                    : "text-slate-600 hover:text-[#0f172a]"
                }`}
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Skill</span>
              </button>
            </div>

            {/* Close Button */}
            <button
              onClick={onClose}
              className="p-2 rounded-xl text-slate-400 hover:text-[#0f172a] hover:bg-slate-100 transition-colors"
              title="Close Modal"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto p-6 bg-white">
          {activeTab === "browse" ? (
            <div className="space-y-5">
              {/* Search & Category Filter Bar */}
              <div className="flex flex-col sm:flex-row items-center gap-3">
                <div className="relative flex-1 w-full">
                  <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <input
                    type="text"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    placeholder="Search by skill name, capability, or keywords..."
                    className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-white border border-[#cbd5e1] text-sm text-[#0f172a] placeholder:text-slate-400 focus:outline-none focus:border-[#0284c7] focus:ring-1 focus:ring-[#0284c7]"
                  />
                </div>

                {/* Categories */}
                <div className="flex items-center gap-1.5 overflow-x-auto w-full sm:w-auto pb-1 sm:pb-0">
                  {categories.map((cat) => (
                    <button
                      key={cat}
                      onClick={() => setSelectedCategory(cat)}
                      className={`px-3 py-1.5 rounded-xl text-xs whitespace-nowrap transition-all font-medium ${
                        selectedCategory === cat
                          ? "bg-[#0284c7] text-white shadow-sm font-bold"
                          : "bg-[#f1f5f9] border border-[#e2e8f0] text-slate-600 hover:text-[#0f172a] hover:bg-[#e2e8f0]"
                      }`}
                    >
                      {cat}
                    </button>
                  ))}
                </div>
              </div>

              {/* Skills Grid */}
              {loading ? (
                <div className="flex flex-col items-center justify-center py-16 text-slate-400 gap-3">
                  <div className="w-8 h-8 border-2 border-[#0284c7] border-t-transparent rounded-full animate-spin" />
                  <span className="text-xs font-mono">Synchronizing Skills Matrix...</span>
                </div>
              ) : filteredSkills.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-slate-400 gap-2 border border-dashed border-[#e2e8f0] rounded-2xl">
                  <Layers className="w-8 h-8 text-slate-300" />
                  <p className="text-sm">No skills found matching your query.</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                  {filteredSkills.map((skill, idx) => {
                    const skillId = skill.id || skill.skill_id || `skill-${idx}`;
                    return (
                      <div
                        key={skillId}
                        className="group relative flex flex-col justify-between p-4 rounded-2xl bg-[#f8fafc] border border-[#e2e8f0] hover:border-[#0284c7] hover:bg-white transition-all shadow-sm"
                      >
                        <div>
                          <div className="flex items-start justify-between gap-2 mb-2">
                            <div className="flex items-center gap-2.5">
                              <span className="text-xl">{skill.icon || "⚡"}</span>
                              <div>
                                <h3 className="text-sm font-bold text-[#0f172a] group-hover:text-[#0284c7] transition-colors">
                                  {skill.name}
                                </h3>
                                <span className="text-[10px] font-mono text-slate-500">
                                  {skillId}
                                </span>
                              </div>
                            </div>
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-200 text-slate-700">
                              {skill.category || "General"}
                            </span>
                          </div>

                          <p className="text-xs text-slate-600 leading-relaxed line-clamp-3 mb-3">
                            {skill.description || "No description provided."}
                          </p>
                        </div>

                        {/* Tags & Action */}
                        <div className="flex items-center justify-between pt-2 border-t border-[#e2e8f0]">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            {skill.tags &&
                              skill.tags.slice(0, 3).map((tag, tIdx) => (
                                <span
                                  key={tIdx}
                                  className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded text-[10px] bg-slate-100 text-slate-600 font-mono"
                                >
                                  <Tag className="w-2.5 h-2.5 text-[#0284c7]" />
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
                              className="px-3.5 py-1 rounded-xl text-xs font-semibold bg-[#0f172a] text-white hover:bg-black transition-all"
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
                <div className="flex items-center gap-2 p-3.5 rounded-xl bg-emerald-50 border border-emerald-300 text-emerald-800 text-xs">
                  <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
                  <span>{submitSuccess}</span>
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Skill Identifier (ID) *
                  </label>
                  <input
                    type="text"
                    required
                    value={formId}
                    onChange={(e) => setFormId(e.target.value)}
                    placeholder="e.g. data_visualizer"
                    className="w-full px-3.5 py-2 rounded-xl bg-white border border-[#cbd5e1] text-sm text-[#0f172a] placeholder:text-slate-400 focus:outline-none focus:border-[#0284c7] font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Display Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={formName}
                    onChange={(e) => setFormName(e.target.value)}
                    placeholder="e.g. Advanced Data Visualizer"
                    className="w-full px-3.5 py-2 rounded-xl bg-white border border-[#cbd5e1] text-sm text-[#0f172a] placeholder:text-slate-400 focus:outline-none focus:border-[#0284c7]"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Category
                  </label>
                  <select
                    value={formCategory}
                    onChange={(e) => setFormCategory(e.target.value)}
                    className="w-full px-3.5 py-2 rounded-xl bg-white border border-[#cbd5e1] text-sm text-[#0f172a] focus:outline-none focus:border-[#0284c7]"
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
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Tags (Comma-separated)
                  </label>
                  <input
                    type="text"
                    value={formTags}
                    onChange={(e) => setFormTags(e.target.value)}
                    placeholder="e.g. chart, plotting, matplotlib"
                    className="w-full px-3.5 py-2 rounded-xl bg-white border border-[#cbd5e1] text-sm text-[#0f172a] placeholder:text-slate-400 focus:outline-none focus:border-[#0284c7] font-mono text-xs"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Brief Summary / Description
                </label>
                <input
                  type="text"
                  value={formDesc}
                  onChange={(e) => setFormDesc(e.target.value)}
                  placeholder="Summarize what this skill enables Ultron to execute"
                  className="w-full px-3.5 py-2 rounded-xl bg-white border border-[#cbd5e1] text-sm text-[#0f172a] placeholder:text-slate-400 focus:outline-none focus:border-[#0284c7]"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Agent Execution Instructions / Prompt Directive *
                </label>
                <textarea
                  required
                  rows={5}
                  value={formInstructions}
                  onChange={(e) => setFormInstructions(e.target.value)}
                  placeholder="Provide precise guidelines, tool workflows, and output format standards for Ultron when using this skill..."
                  className="w-full px-3.5 py-2 rounded-xl bg-white border border-[#cbd5e1] text-sm text-[#0f172a] placeholder:text-slate-400 focus:outline-none focus:border-[#0284c7] font-mono text-xs leading-relaxed"
                />
              </div>

              <div className="flex justify-end pt-3">
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-[#0f172a] text-white font-bold text-sm hover:bg-black transition-all shadow-md disabled:opacity-50"
                >
                  {submitting ? (
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
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

