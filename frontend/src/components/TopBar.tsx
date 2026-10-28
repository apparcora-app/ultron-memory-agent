import React, { useState, useEffect } from "react";
import {
  ChevronDown,
  Menu,
  Moon,
  Sun,
} from "lucide-react";

interface TopBarProps {
  operationMode?: "DIRECT" | "SWARM";
  selectedModel?: string;
  sessionTitle?: string;
  isCanvasOpen?: boolean;
  onToggleCanvas?: () => void;
  isStreamConnected?: boolean;
  onOpenSettings?: () => void;
  onOpenMemories?: () => void;
  onToggleMobileSidebar?: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({
  onOpenSettings,
  onToggleMobileSidebar,
}) => {
  const [showStatusModal, setShowStatusModal] = useState(false);
  const [currentTheme, setCurrentTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    if (typeof document !== "undefined") {
      const activeTheme = (document.documentElement.getAttribute("data-theme") as "dark" | "light") || "dark";
      setCurrentTheme(activeTheme);
    }
  }, []);

  const toggleTheme = () => {
    const nextTheme = currentTheme === "dark" ? "light" : "dark";
    setCurrentTheme(nextTheme);
    if (typeof document !== "undefined") {
      document.documentElement.setAttribute("data-theme", nextTheme);
      try {
        localStorage.setItem("ultron-theme", nextTheme);
      } catch {
        // ignore storage errors
      }
    }
  };

  return (
    <header className="flex items-center justify-between px-3 sm:px-5 py-2.5 bg-theme-panel/95 border-b border-theme-border backdrop-blur-md z-20 shrink-0 select-none transition-colors">
      {/* ── Left: Mobile Hamburger & Version Pill Dropdown ── */}
      <div className="flex items-center gap-2 sm:gap-3">
        {onToggleMobileSidebar && (
          <button
            type="button"
            onClick={onToggleMobileSidebar}
            className="md:hidden flex items-center justify-center min-w-[44px] min-h-[44px] p-2 rounded-xl text-theme-muted hover:text-theme-main hover:bg-theme-card transition-colors"
            title="Open Directives Drawer"
            aria-label="Open Directives Drawer"
          >
            <Menu className="w-5 h-5" />
          </button>
        )}

        <button
          onClick={() => setShowStatusModal(!showStatusModal)}
          className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-theme-card border border-theme-border text-xs font-medium text-theme-main hover:border-theme-focus transition-all shadow-xs min-h-[36px]"
        >
          <span className="w-2 h-2 rounded-full bg-theme-accent animate-pulse" />
          <span className="font-sans font-semibold">Ultron v4.5</span>
          <ChevronDown className="w-3.5 h-3.5 text-theme-muted" />
        </button>
      </div>

      {/* ── Right: Theme Switcher, Navigation Links & User Avatar ── */}
      <div className="flex items-center gap-2 sm:gap-4 text-xs font-medium text-theme-muted">
        {/* Theme Switcher Button */}
        <button
          type="button"
          onClick={toggleTheme}
          className="flex items-center justify-center min-w-[44px] min-h-[44px] p-2 rounded-xl border border-theme-border bg-theme-card hover:bg-theme-dock text-theme-muted hover:text-theme-main transition-colors shadow-xs"
          title={`Switch to ${currentTheme === "dark" ? "Crisp Light" : "Obsidian Dark"} Theme`}
          aria-label={`Switch to ${currentTheme === "dark" ? "Crisp Light" : "Obsidian Dark"} Theme`}
        >
          {currentTheme === "dark" ? (
            <Sun className="w-4 h-4 text-amber-400" />
          ) : (
            <Moon className="w-4 h-4 text-theme-accent" />
          )}
        </button>

        <a
          href="#dashboard"
          className="text-theme-main font-semibold hover:text-theme-accent transition-colors px-1 py-2 min-h-[44px] flex items-center"
        >
          Dashboard
        </a>

        <button
          type="button"
          onClick={onOpenSettings}
          className="hover:text-theme-main transition-colors hidden sm:flex items-center px-1 py-2 min-h-[44px]"
        >
          Settings
        </button>

        <a
          href="https://github.com/apparcora-app/ultron-memory-agent"
          target="_blank"
          rel="noreferrer"
          className="hover:text-theme-main transition-colors hidden md:flex items-center px-1 py-2 min-h-[44px]"
        >
          Help & Support
        </a>

        {/* User Profile Avatar */}
        <div className="relative cursor-pointer group min-w-[44px] min-h-[44px] flex items-center justify-center">
          <div className="w-8 h-8 rounded-full bg-theme-accent flex items-center justify-center text-xs font-bold text-white shadow-xs ring-2 ring-theme-panel">
            HR
          </div>
        </div>
      </div>
    </header>
  );
};
