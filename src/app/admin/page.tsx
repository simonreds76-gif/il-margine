"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import dynamic from "next/dynamic";
import { supabase, Bet, Bookmaker } from "@/lib/supabase";
import { formatOdds } from "@/lib/format";
import { stripTipSeoMarker } from "@/lib/tip-seo";

const MonthlyBreakdown = dynamic(() => import("@/components/MonthlyBreakdown"), {
  ssr: false,
  loading: () => (
    <div className="rounded-lg border border-slate-800 bg-slate-900/40 px-4 py-6 text-sm text-slate-500">
      Loading monthly breakdown...
    </div>
  ),
});

const SETTING_KEYS = {
  combined: "monthly_breakdown_combined_public",
  props: "monthly_breakdown_props_public",
  tennis: "monthly_breakdown_tennis_public",
} as const;

export default function AdminPanel() {
  const [isLoggedIn, setIsLoggedIn] = useState(
    () => typeof window !== "undefined" && localStorage.getItem("admin_logged_in") === "true"
  );
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [activeTab, setActiveTab] = useState<"add" | "pending" | "recent" | "settings">("add");
  const [bookmakers, setBookmakers] = useState<Bookmaker[]>([]);
  const [pendingBets, setPendingBets] = useState<Bet[]>([]);
  const [pendingCount, setPendingCount] = useState<number | null>(null);
  const [recentBets, setRecentBets] = useState<Bet[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [editingBet, setEditingBet] = useState<Bet | null>(null);
  const [monthlyBreakdownPublic, setMonthlyBreakdownPublic] = useState<Record<string, boolean>>({
    combined: false,
    props: false,
    tennis: false,
  });
  const [settingsLoading, setSettingsLoading] = useState<string | null>(null);
  const [adminError, setAdminError] = useState<string | null>(null);
  const [tennisRefreshLoading, setTennisRefreshLoading] = useState(false);
  const [tennisRefreshMessage, setTennisRefreshMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [tennisRefreshRequestId, setTennisRefreshRequestId] = useState<string | null>(null);
  const loadedTabsRef = useRef({
    bookmakers: false,
    pending: false,
    recent: false,
    settings: false,
  });
  const [editForm, setEditForm] = useState({
    market: "props" as "props" | "tennis" | "betbuilders" | "atg",
    category: "",
    event: "",
    player: "",
    selection: "",
    odds: "",
    bookmaker_id: "",
    stake: "1",
    match_date: "",
    notes: "",
    status: "won" as "won" | "lost" | "void",
  });

  // Form state
  const [form, setForm] = useState({
    market: "props" as "props" | "tennis" | "betbuilders" | "atg",
    category: "",
    event: "",
    player: "",
    selection: "",
    odds: "",
    bookmaker_id: "",
    stake: "1",
    match_date: new Date().toISOString().slice(0, 10),
    notes: "",
  });

  const categories = {
    props: [
      { id: "pl", name: "Premier League" },
      { id: "seriea", name: "Serie A" },
      { id: "laliga", name: "La Liga" },
      { id: "bundesliga", name: "Bundesliga" },
      { id: "ligue1", name: "Ligue 1" },
      { id: "ucl", name: "Champions League" },
      { id: "worldcup", name: "World Cup" },
      { id: "other", name: "Other" },
    ],
    tennis: [
      { id: "atp", name: "ATP Tour" },
      { id: "challenger", name: "Challenger" },
      { id: "ausopen", name: "Australian Open" },
      { id: "rolandgarros", name: "Roland Garros" },
      { id: "wimbledon", name: "Wimbledon" },
      { id: "usopen", name: "US Open" },
      { id: "other", name: "Other" },
    ],
    betbuilders: [
      { id: "pl", name: "Premier League" },
      { id: "seriea", name: "Serie A" },
      { id: "laliga", name: "La Liga" },
      { id: "bundesliga", name: "Bundesliga" },
      { id: "ligue1", name: "Ligue 1" },
      { id: "worldcup", name: "World Cup" },
      { id: "other", name: "Other" },
    ],
    atg: [
      { id: "pl", name: "Premier League" },
      { id: "seriea", name: "Serie A" },
      { id: "laliga", name: "La Liga" },
      { id: "bundesliga", name: "Bundesliga" },
      { id: "ligue1", name: "Ligue 1" },
      { id: "worldcup", name: "World Cup" },
      { id: "other", name: "Other" },
    ],
  };

  const handleLogin = async () => {
    setMessage(null);
    const res = await fetch("/api/admin/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    const data = await res.json().catch(() => ({}));
    if (res.ok && data.ok) {
      setIsLoggedIn(true);
      localStorage.setItem("admin_logged_in", "true");
    } else {
      setMessage({ type: "error", text: data.error || "Wrong password" });
    }
  };

  const fetchSettings = useCallback(async () => {
    try {
      const keys = Object.values(SETTING_KEYS);
      const { data: rows } = await supabase.from("site_settings").select("key, value").in("key", keys);
      const result: Record<string, boolean> = { combined: false, props: false, tennis: false };
      for (const key of keys) {
        const scope = key === SETTING_KEYS.combined ? "combined" : key === SETTING_KEYS.props ? "props" : "tennis";
        result[scope] = rows?.find((r) => r.key === key)?.value === true;
      }
      setMonthlyBreakdownPublic(result);
    } catch (e) {
      console.error("fetchSettings:", e);
      setAdminError("Could not load settings. Check Supabase env vars.");
    }
  }, []);

  const toggleMonthlyBreakdownPublic = async (scope: "combined" | "props" | "tennis") => {
    setSettingsLoading(scope);
    setMessage(null);
    const key = SETTING_KEYS[scope];
    const newVal = !monthlyBreakdownPublic[scope];
    const res = await fetch("/api/admin/settings", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key, value: newVal }),
    });
    const data = await res.json().catch(() => ({}));
    setSettingsLoading(null);
    if (res.ok) {
      setMonthlyBreakdownPublic((prev) => ({ ...prev, [scope]: newVal }));
      const labels = { combined: "Homepage (combined)", props: "Player Props", tennis: "Tennis" };
      setMessage({ type: "success", text: `${labels[scope]}: ${newVal ? "now public" : "now hidden"}` });
    } else {
      setMessage({ type: "error", text: data.error || "Failed to update" });
    }
  };

  const fetchBookmakers = useCallback(async () => {
    try {
      const { data, error } = await supabase
        .from("bookmakers")
        .select("*")
        .eq("active", true)
        .order("name");
      if (data) setBookmakers(data);
      if (error) console.error("Bookmakers error:", error);
    } catch (e) {
      console.error("fetchBookmakers:", e);
      setAdminError("Could not connect to Supabase. Check NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.");
    }
  }, []);

  const fetchPendingBets = useCallback(async () => {
    try {
      const { data, error } = await supabase
        .from("bets")
        .select("*, bookmaker:bookmakers(*)")
        .eq("status", "pending")
        .order("posted_at", { ascending: false });
      if (data) {
        setPendingBets(data);
        setPendingCount(data.length);
      }
      if (error) console.error("Pending bets error:", error);
    } catch (e) {
      console.error("fetchPendingBets:", e);
      if (!adminError) setAdminError("Could not load data.");
    }
  }, [adminError]);

  const fetchPendingCount = useCallback(async () => {
    try {
      const { count, error } = await supabase
        .from("bets")
        .select("*", { count: "exact", head: true })
        .eq("status", "pending");
      if (error) {
        console.error("Pending bet count error:", error);
        return;
      }
      setPendingCount(count ?? 0);
    } catch (e) {
      console.error("fetchPendingCount:", e);
    }
  }, []);

  const fetchRecentBets = useCallback(async () => {
    try {
      const { data, error } = await supabase
        .from("bets")
        .select("*, bookmaker:bookmakers(*)")
        .in("status", ["won", "lost", "void"])
        .order("settled_at", { ascending: false })
        .limit(50);
      if (data) setRecentBets(data);
      if (error) console.error("Recent bets error:", error);
    } catch (e) {
      console.error("fetchRecentBets:", e);
      if (!adminError) setAdminError("Could not load data.");
    }
  }, [adminError]);

  const ensureTabData = useCallback(
    async (tab: typeof activeTab) => {
      if (tab === "add" && !loadedTabsRef.current.bookmakers) {
        loadedTabsRef.current.bookmakers = true;
        await fetchBookmakers();
      }

      if (tab === "pending" && !loadedTabsRef.current.pending) {
        loadedTabsRef.current.pending = true;
        await fetchPendingBets();
      }

      if (tab === "recent" && !loadedTabsRef.current.recent) {
        loadedTabsRef.current.recent = true;
        await fetchRecentBets();
      }

      if (tab === "settings" && !loadedTabsRef.current.settings) {
        loadedTabsRef.current.settings = true;
        await fetchSettings();
      }
    },
    [fetchBookmakers, fetchPendingBets, fetchRecentBets, fetchSettings]
  );

  // Lazy-load tab data so the initial admin screen doesn't fetch everything at once.
  useEffect(() => {
    if (!isLoggedIn) return;

    const timeoutId = window.setTimeout(() => {
      void fetchPendingCount();
      void ensureTabData(activeTab);
    }, 0);

    return () => window.clearTimeout(timeoutId);
  }, [activeTab, ensureTabData, fetchPendingCount, isLoggedIn]);

  const handleAddBet = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanNotes = stripTipSeoMarker(form.notes);
    setLoading(true);
    setMessage(null);
    const res = await fetch("/api/admin/bets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        market: form.market,
        category: form.category,
        event: form.event,
        player: form.player || null,
        selection: form.selection,
        odds: parseFloat(form.odds),
        bookmaker_id: parseInt(form.bookmaker_id),
        stake: Math.round(parseFloat(form.stake) * 100) / 100,
        match_date: form.match_date || null,
        notes: cleanNotes || null,
      }),
    });
    const data = await res.json().catch(() => ({}));
    setLoading(false);
    if (res.ok) {
      let successText = "Bet added successfully!";
      if (data.telegram?.status === "posted") {
        successText += " Telegram posted.";
      } else if (data.telegram?.status === "failed") {
        successText += ` Telegram failed: ${data.telegram.reason || "unknown error"}`;
      } else if (form.market === "props" && form.category === "worldcup" && data.telegram?.status === "skipped") {
        successText += ` Telegram not posted (${data.telegram.reason || "skipped"}).`;
      }
      setMessage({ type: "success", text: successText });
      setForm({
        ...form,
        event: "",
        player: "",
        selection: "",
        odds: "",
        match_date: new Date().toISOString().slice(0, 10),
        notes: "",
      });
      fetchPendingBets();
      fetchPendingCount();
    } else {
      setMessage({ type: "error", text: data.error || "Failed to add bet" });
    }
  };

  const handleSettle = async (betId: number, status: "won" | "lost" | "void") => {
    setLoading(true);
    setMessage(null);
    const { data: bet, error: fetchError } = await supabase.from("bets").select("odds, stake").eq("id", betId).single();
    if (fetchError || !bet) {
      setLoading(false);
      setMessage({ type: "error", text: "Failed to fetch bet details" });
      return;
    }
    let profitLoss: number;
    if (status === "won") profitLoss = Number(bet.odds) * Number(bet.stake) - Number(bet.stake);
    else if (status === "lost") profitLoss = -Number(bet.stake);
    else profitLoss = 0;
    const res = await fetch("/api/admin/bets", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: betId, status, profit_loss: profitLoss, settled_at: new Date().toISOString() }),
    });
    const data = await res.json().catch(() => ({}));
    setLoading(false);
    if (res.ok) {
      setMessage({ type: "success", text: `Bet marked as ${status}. P/L: ${profitLoss > 0 ? "+" : ""}${profitLoss.toFixed(2)}u` });
      await fetchPendingBets();
      await fetchPendingCount();
      await fetchRecentBets();
    } else {
      setMessage({ type: "error", text: data.error || "Failed to settle" });
    }
  };

  const handleTelegramPost = async (betId: number) => {
    setLoading(true);
    setMessage(null);
    const res = await fetch("/api/admin/bets", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: betId, action: "post_telegram" }),
    });
    const data = await res.json().catch(() => ({}));
    setLoading(false);
    if (res.ok) {
      setMessage({ type: "success", text: "Player-prop alert posted to Telegram." });
    } else {
      setMessage({ type: "error", text: data.error || "Failed to post player-prop alert" });
    }
  };

  const handleDelete = async (betId: number) => {
    if (!confirm("Are you sure you want to delete this bet?")) return;
    const res = await fetch(`/api/admin/bets?id=${betId}`, { method: "DELETE" });
    const data = await res.json().catch(() => ({}));
    if (res.ok) {
      setMessage({ type: "success", text: "Bet deleted" });
      fetchPendingBets();
      fetchPendingCount();
      fetchRecentBets();
    } else {
      setMessage({ type: "error", text: data.error || "Failed to delete" });
    }
  };

  const handleTennisRefresh = async () => {
    setTennisRefreshLoading(true);
    setTennisRefreshMessage(null);
    const res = await fetch("/api/admin/tennis-refresh", { method: "POST" });
    const data = await res.json().catch(() => ({}));
    if (res.ok) {
      setTennisRefreshRequestId(data.command?.request_id || null);
      setTennisRefreshMessage({
        type: "success",
        text: data.message || "Fair-odds refresh queued. Waiting for the laptop pipeline.",
      });
    } else if (res.status === 409 && data.command?.request_id) {
      setTennisRefreshRequestId(data.command.request_id);
      setTennisRefreshMessage({
        type: "success",
        text: "A fair-odds refresh is already active. Following that run instead of creating a duplicate.",
      });
    } else {
      setTennisRefreshLoading(false);
      setTennisRefreshMessage({ type: "error", text: data.error || "Unable to start tennis refresh" });
    }
  };

  useEffect(() => {
    if (!tennisRefreshRequestId) return;
    let cancelled = false;

    const poll = async () => {
      const res = await fetch(`/api/admin/tennis-refresh?request_id=${encodeURIComponent(tennisRefreshRequestId)}`, {
        cache: "no-store",
      });
      const data = await res.json().catch(() => ({}));
      if (cancelled) return;
      if (!res.ok) {
        setTennisRefreshLoading(false);
        setTennisRefreshRequestId(null);
        setTennisRefreshMessage({ type: "error", text: data.error || "Unable to read tennis refresh status" });
        return;
      }

      const command = data.command || {};
      const state = String(command.state || "pending");
      if (state === "completed") {
        const count = Number(command.signal_count || 0);
        setTennisRefreshLoading(false);
        setTennisRefreshRequestId(null);
        setTennisRefreshMessage({
          type: "success",
          text: `Completed: ${count} current tennis signal${count === 1 ? "" : "s"}. Telegram relay queued successfully.`,
        });
      } else if (state === "failed") {
        setTennisRefreshLoading(false);
        setTennisRefreshRequestId(null);
        setTennisRefreshMessage({ type: "error", text: command.error || "Fair-odds refresh failed" });
      } else {
        const label = state === "waiting"
          ? "Waiting for the current tennis job to finish..."
          : state === "started"
            ? "Running on the laptop. Fair odds normally take 10-20 minutes..."
            : "Queued for the laptop; pickup normally takes under two minutes...";
        setTennisRefreshMessage({ type: "success", text: label });
      }
    };

    void poll();
    const timer = window.setInterval(() => void poll(), 5_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [tennisRefreshRequestId]);

  // Open edit modal
  const openEdit = (bet: Bet) => {
    setEditingBet(bet);
    setEditForm({
      market: bet.market,
      category: bet.category,
      event: bet.event,
      player: bet.player || "",
      selection: bet.selection,
      odds: String(bet.odds),
      bookmaker_id: String(bet.bookmaker_id),
      stake: String(bet.stake),
      match_date: bet.match_date ? bet.match_date.slice(0, 10) : new Date().toISOString().slice(0, 10),
      notes: stripTipSeoMarker(bet.notes),
      status: (bet.status === "won" || bet.status === "lost" || bet.status === "void" ? bet.status : "won") as "won" | "lost" | "void",
    });
  };

  // Save edited bet (updates DB; stats recalc automatically from DB + baseline)
  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingBet) return;
    const cleanNotes = stripTipSeoMarker(editForm.notes);
    setLoading(true);
    setMessage(null);

    const payload: Record<string, unknown> = {
      market: editForm.market,
      category: editForm.category,
      event: editForm.event,
      player: editForm.player || null,
      selection: editForm.selection,
      odds: parseFloat(editForm.odds),
      bookmaker_id: parseInt(editForm.bookmaker_id),
      stake: Math.round(parseFloat(editForm.stake) * 100) / 100,
      match_date: editForm.match_date || null,
      notes: cleanNotes || null,
    };

    // If settled, include status and recalc profit_loss from new odds/stake/status
    if (editingBet.status && ["won", "lost", "void"].includes(editingBet.status)) {
      const status = editForm.status;
      payload.status = status;
      const stake = parseFloat(editForm.stake);
      const odds = parseFloat(editForm.odds);
      if (status === "won") {
        payload.profit_loss = odds * stake - stake;
      } else if (status === "lost") {
        payload.profit_loss = -stake;
      } else {
        payload.profit_loss = 0;
      }
    }

    const res = await fetch("/api/admin/bets", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: editingBet.id, ...payload }),
    });
    const data = await res.json().catch(() => ({}));
    setLoading(false);
    if (res.ok) {
      setMessage({ type: "success", text: "Pick updated. Stats will reflect the change." });
      setEditingBet(null);
      await fetchPendingBets();
      await fetchPendingCount();
      await fetchRecentBets();
    } else {
      setMessage({ type: "error", text: data.error || "Failed to update" });
    }
  };

  // Login screen
  if (!isLoggedIn) {
    return (
      <div className="min-h-screen bg-[#0f1117] text-slate-100 flex items-center justify-center">
        <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-8 w-full max-w-sm">
          <h1 className="text-2xl font-bold mb-6 text-center">Admin Login</h1>
          <div className="relative">
            <input
              type={showPassword ? "text" : "password"}
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleLogin()}
              className="w-full bg-slate-800 border border-slate-700 rounded px-4 py-3 mb-4 focus:outline-none focus:border-emerald-500 pr-12"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-3 text-slate-500 hover:text-slate-300"
            >
              {showPassword ? (
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                </svg>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                </svg>
              )}
            </button>
          </div>
          <button
            onClick={handleLogin}
            className="w-full bg-emerald-500 hover:bg-emerald-400 text-black font-medium py-3 rounded transition-colors"
          >
            Login
          </button>
          {message && (
            <p className={`mt-4 text-sm text-center ${message.type === "error" ? "text-red-400" : "text-emerald-400"}`}>
              {message.text}
            </p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      {/* Header */}
      <header className="border-b border-slate-800 p-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <h1 className="text-xl font-bold">Il Margine Admin</h1>
          <button
            onClick={async () => {
              await fetch("/api/admin/logout", { method: "POST" });
              localStorage.removeItem("admin_logged_in");
              setIsLoggedIn(false);
            }}
            className="text-sm text-slate-400 hover:text-slate-100"
          >
            Logout
          </button>
        </div>
      </header>

      <section className="border-b border-slate-800 bg-slate-950/40">
          <div className="max-w-4xl mx-auto px-4 py-4">
            <div className="flex flex-col gap-3 rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-300">On-demand tennis</div>
                <h2 className="mt-1 font-semibold text-slate-100">Fair odds + Telegram alerts</h2>
                <p className="mt-1 text-xs text-slate-400">
                  Starts the existing AM pipeline now on localhost, or queues it securely for the laptop from the hosted Admin. Duplicate runs are blocked.
                </p>
              </div>
              <button
                type="button"
                onClick={handleTennisRefresh}
                disabled={tennisRefreshLoading}
                className="shrink-0 rounded-lg border border-cyan-400/40 bg-cyan-400/15 px-4 py-3 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-400/25 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {tennisRefreshLoading ? "Refresh in progress..." : "Run fair odds + alerts"}
              </button>
            </div>
            {tennisRefreshMessage && (
              <p className={`mt-2 text-sm ${tennisRefreshMessage.type === "success" ? "text-emerald-400" : "text-red-400"}`}>
                {tennisRefreshMessage.text}
              </p>
            )}
          </div>
      </section>

      {/* Tabs */}
      <div className="border-b border-slate-800">
        <div className="max-w-4xl mx-auto flex">
          {[
            { id: "add", label: "Add Bet" },
            { id: "pending", label: "Pending", count: pendingCount },
            { id: "recent", label: "Recent" },
            { id: "settings", label: "Settings" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as typeof activeTab)}
              className={`px-6 py-4 text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? "text-emerald-400 border-b-2 border-emerald-400"
                  : "text-slate-400 hover:text-slate-100"
              }`}
            >
              <span>{tab.label}</span>
              {tab.id === "pending" && tab.count != null ? (
                <span
                  className={`ml-2 inline-flex min-w-6 items-center justify-center rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                    activeTab === tab.id ? "bg-emerald-500/20 text-emerald-300" : "bg-slate-800 text-slate-300"
                  }`}
                >
                  {tab.count}
                </span>
              ) : null}
            </button>
          ))}
        </div>
      </div>

      {/* Admin error (e.g. missing Supabase env vars) */}
      {adminError && (
        <div className="max-w-4xl mx-auto mt-4 px-4">
          <div className="p-3 rounded text-sm bg-red-500/10 text-red-400 border border-red-500/30">
            {adminError} Ensure env vars are set for Preview deployments in Vercel.
          </div>
        </div>
      )}

      {/* Message */}
      {message && (
        <div className={`max-w-4xl mx-auto mt-4 px-4`}>
          <div
            className={`p-3 rounded text-sm ${
              message.type === "error"
                ? "bg-red-500/10 text-red-400 border border-red-500/30"
                : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
            }`}
          >
            {message.text}
          </div>
        </div>
      )}

      {/* Content */}
      <div className="max-w-4xl mx-auto p-4">
        {/* ADD BET TAB */}
        {activeTab === "add" && (
          <form onSubmit={handleAddBet} className="space-y-4">
            {/* Market & Category */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-slate-500 mb-1">Market</label>
                <select
                  value={form.market}
                  onChange={(e) => {
                    setForm({
                      ...form,
                      market: e.target.value as typeof form.market,
                      category: "",
                    });
                  }}
                  className="w-full bg-slate-800 border border-slate-700 rounded px-4 py-3 focus:outline-none focus:border-emerald-500"
                >
                  <option value="props">Player Props</option>
                  <option value="tennis">ATP Tennis</option>
                  <option value="betbuilders">Bet Builders</option>
                  <option value="atg">ATG</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">Category</label>
                <select
                  value={form.category}
                  onChange={(e) => setForm({ ...form, category: e.target.value })}
                  required
                  className="w-full bg-slate-800 border border-slate-700 rounded px-4 py-3 focus:outline-none focus:border-emerald-500"
                >
                  <option value="">Select...</option>
                  {categories[form.market].map((cat) => (
                    <option key={cat.id} value={cat.id}>
                      {cat.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Event */}
            <div>
              <label className="block text-xs text-slate-500 mb-1">Event</label>
              <input
                type="text"
                placeholder="e.g. Arsenal vs Chelsea"
                value={form.event}
                onChange={(e) => setForm({ ...form, event: e.target.value })}
                required
                className="w-full bg-slate-800 border border-slate-700 rounded px-4 py-3 focus:outline-none focus:border-emerald-500"
              />
            </div>

            {/* Match date */}
            <div>
              <label className="block text-xs text-slate-500 mb-1">Match date</label>
              <input
                type="date"
                value={form.match_date}
                onChange={(e) => setForm({ ...form, match_date: e.target.value })}
                required
                className="w-full bg-slate-800 border border-slate-700 rounded px-4 py-3 focus:outline-none focus:border-emerald-500"
              />
            </div>

            {/* Player (optional) - props: player name; tennis: pick for match odds (e.g. Buse for ML) */}
            {(form.market === "props" || form.market === "tennis") && (
              <div>
                <label className="block text-xs text-slate-500 mb-1">Player</label>
                <input
                  type="text"
                  placeholder={form.market === "tennis" ? "e.g. Buse (for match odds / ML)" : "e.g. Saka"}
                  value={form.player}
                  onChange={(e) => setForm({ ...form, player: e.target.value })}
                  className="w-full bg-slate-800 border border-slate-700 rounded px-4 py-3 focus:outline-none focus:border-emerald-500"
                />
              </div>
            )}

            {/* Selection */}
            <div>
              <label className="block text-xs text-slate-500 mb-1">Selection</label>
              <input
                type="text"
                placeholder={form.market === "tennis" ? "e.g. ML or Game handicap -2.5" : "e.g. Over 2.5 Shots"}
                value={form.selection}
                onChange={(e) => setForm({ ...form, selection: e.target.value })}
                required
                className="w-full bg-slate-800 border border-slate-700 rounded px-4 py-3 focus:outline-none focus:border-emerald-500"
              />
            </div>

            {/* Odds, Bookmaker, Stake */}
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-xs text-slate-500 mb-1">Odds</label>
                <input
                  type="number"
                  step="0.01"
                  min="1.01"
                  placeholder="1.85"
                  value={form.odds}
                  onChange={(e) => setForm({ ...form, odds: e.target.value })}
                  required
                  className="w-full bg-slate-800 border border-slate-700 rounded px-4 py-3 focus:outline-none focus:border-emerald-500"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">Bookmaker</label>
                <select
                  value={form.bookmaker_id}
                  onChange={(e) => setForm({ ...form, bookmaker_id: e.target.value })}
                  required
                  className="w-full bg-slate-800 border border-slate-700 rounded px-4 py-3 focus:outline-none focus:border-emerald-500"
                >
                  <option value="">Select...</option>
                  {bookmakers.map((bk) => (
                    <option key={bk.id} value={bk.id}>
                      {bk.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">Stake (units)</label>
                <input
                  type="number"
                  step="0.05"
                  min="0.1"
                  max="5"
                  value={form.stake}
                  onChange={(e) => setForm({ ...form, stake: e.target.value })}
                  required
                  className="w-full bg-slate-800 border border-slate-700 rounded px-4 py-3 focus:outline-none focus:border-emerald-500"
                />
              </div>
            </div>

            {/* Notes */}
            <div>
              <label className="mb-1 block text-xs text-slate-500">Notes (optional)</label>
              <textarea
                rows={3}
                placeholder="Optional context for the pick."
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                className="w-full resize-y bg-slate-800 border border-slate-700 rounded px-4 py-3 focus:outline-none focus:border-emerald-500"
              />
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-emerald-500 hover:bg-emerald-400 disabled:bg-slate-700 text-black font-medium py-4 rounded transition-colors"
            >
              {loading ? "Adding..." : "Add Bet"}
            </button>
          </form>
        )}

        {/* PENDING BETS TAB */}
        {activeTab === "pending" && (
          <div className="space-y-3">
            {pendingBets.length === 0 ? (
              <p className="text-slate-500 text-center py-8">No pending bets</p>
            ) : (
              pendingBets.map((bet) => (
                <div
                  key={bet.id}
                  className="bg-slate-900/50 border border-slate-800 rounded-lg p-4"
                >
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <span className="text-xs text-slate-500 uppercase">
                        {bet.market} • {bet.category}
                      </span>
                      <h3 className="font-medium">{bet.event}</h3>
                      {bet.player && (
                        <p className="text-sm text-slate-400">{bet.player}</p>
                      )}
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-mono text-emerald-400">
                        {formatOdds(bet.odds)}
                      </div>
                      <div className="text-xs text-slate-500">
                        {bet.bookmaker?.short_name}
                      </div>
                    </div>
                  </div>
                  <div className="bg-slate-800/50 rounded px-3 py-2 mb-3">
                    <span className="font-medium">{bet.selection}</span>
                    <span className="text-slate-500 ml-2">• {bet.stake}u</span>
                  </div>
                  <div className="flex gap-2 flex-wrap">
                    <button
                      onClick={() => openEdit(bet)}
                      disabled={loading}
                      className="px-3 bg-slate-700/50 hover:bg-slate-600 text-slate-300 py-2 rounded text-sm transition-colors"
                    >
                      Edit
                    </button>
                    {bet.market === "props" && (
                      <button
                        onClick={() => handleTelegramPost(bet.id)}
                        disabled={loading}
                        className="px-3 bg-sky-500/20 hover:bg-sky-500/30 text-sky-300 py-2 rounded text-sm font-medium transition-colors"
                      >
                        Post to Telegram
                      </button>
                    )}
                    <button
                      onClick={() => handleSettle(bet.id, "won")}
                      disabled={loading}
                      className="flex-1 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 py-2 rounded font-medium transition-colors"
                    >
                      Won
                    </button>
                    <button
                      onClick={() => handleSettle(bet.id, "lost")}
                      disabled={loading}
                      className="flex-1 bg-red-500/20 hover:bg-red-500/30 text-red-400 py-2 rounded font-medium transition-colors"
                    >
                      Lost
                    </button>
                    <button
                      onClick={() => handleSettle(bet.id, "void")}
                      disabled={loading}
                      className="flex-1 bg-slate-700/50 hover:bg-slate-700 text-slate-400 py-2 rounded font-medium transition-colors"
                    >
                      Void
                    </button>
                    <button
                      onClick={() => handleDelete(bet.id)}
                      disabled={loading}
                      className="px-3 bg-slate-800 hover:bg-slate-700 text-slate-500 py-2 rounded transition-colors"
                    >
                      🗑
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* SETTINGS TAB */}
        {activeTab === "settings" && (
          <div className="space-y-8">
            <p className="text-sm text-slate-400">
              Control which monthly breakdowns are visible on each page. You can show props when they&apos;re profitable while keeping tennis hidden.
            </p>
            {[
              { scope: "combined" as const, label: "Homepage", desc: "Tennis + props combined" },
              { scope: "props" as const, label: "Player Props page", desc: "Props only" },
              { scope: "tennis" as const, label: "Tennis page", desc: "Tennis only" },
            ].map(({ scope, label, desc }) => (
              <div key={scope} className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
                <div className="flex flex-wrap items-center justify-between gap-4 mb-3">
                  <div>
                    <h3 className="font-semibold">{label}</h3>
                    <p className="text-xs text-slate-500">{desc}</p>
                  </div>
                  <button
                    onClick={() => toggleMonthlyBreakdownPublic(scope)}
                    disabled={settingsLoading === scope}
                    className={`px-4 py-2 rounded font-medium transition-colors ${
                      monthlyBreakdownPublic[scope]
                        ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/50 hover:bg-emerald-500/30"
                        : "bg-slate-700/50 text-slate-400 border border-slate-600 hover:bg-slate-700"
                    }`}
                  >
                    {monthlyBreakdownPublic[scope] ? "Public (click to hide)" : "Hidden (click to show)"}
                  </button>
                </div>
                <MonthlyBreakdown scope={scope} showAll />
              </div>
            ))}
          </div>
        )}

        {/* RECENT BETS TAB */}
        {activeTab === "recent" && (
          <div className="space-y-2">
            {recentBets.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-slate-500">No settled bets yet</p>
                <button 
                  onClick={fetchRecentBets}
                  className="mt-2 text-sm text-emerald-400 hover:underline"
                >
                  Refresh
                </button>
              </div>
            ) : (
              recentBets.map((bet) => (
                <div
                  key={bet.id}
                  className="bg-slate-900/50 border border-slate-800 rounded-lg p-3 flex items-center justify-between"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-xs font-mono px-2 py-0.5 rounded ${
                          bet.status === "won"
                            ? "bg-emerald-500/20 text-emerald-400"
                            : bet.status === "lost"
                            ? "bg-red-500/20 text-red-400"
                            : "bg-slate-700 text-slate-400"
                        }`}
                      >
                        {bet.status.toUpperCase()}
                      </span>
                      <span className="text-xs text-slate-500 uppercase">{bet.market}</span>
                      <span className="text-sm text-slate-400">{bet.event}</span>
                    </div>
                    <p className="text-sm mt-1">
                      {bet.player && <span className="text-slate-500">{bet.player}: </span>}
                      {bet.selection}{" "}
                      <span className="text-slate-500">
                        @ {formatOdds(bet.odds)} • {bet.stake}u
                      </span>
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <div
                      className={`text-lg font-mono font-bold ${
                        bet.profit_loss && bet.profit_loss > 0
                          ? "text-emerald-400"
                          : bet.profit_loss && bet.profit_loss < 0
                          ? "text-red-400"
                          : "text-slate-500"
                      }`}
                    >
                      {bet.profit_loss && bet.profit_loss > 0 ? "+" : ""}
                      {bet.profit_loss?.toFixed(2)}u
                    </div>
                    <button
                      onClick={() => openEdit(bet)}
                      className="text-slate-500 hover:text-emerald-400 text-sm"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDelete(bet.id)}
                      className="text-slate-600 hover:text-red-400 text-sm"
                    >
                      🗑
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Edit bet modal */}
      {editingBet && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60" onClick={() => setEditingBet(null)}>
          <div className="bg-slate-900 border border-slate-700 rounded-xl max-w-lg w-full max-h-[90vh] overflow-y-auto shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="p-4 border-b border-slate-800 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Edit pick</h2>
              <button type="button" onClick={() => setEditingBet(null)} className="text-slate-500 hover:text-slate-300">✕</button>
            </div>
            <form onSubmit={handleSaveEdit} className="p-4 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Market</label>
                  <select
                    value={editForm.market}
                    onChange={(e) => setEditForm({ ...editForm, market: e.target.value as typeof editForm.market, category: "" })}
                    className="w-full bg-slate-800 border border-slate-700 rounded px-4 py-3 focus:outline-none focus:border-emerald-500"
                  >
                    <option value="props">Player Props</option>
                    <option value="tennis">ATP Tennis</option>
                    <option value="betbuilders">Bet Builders</option>
                    <option value="atg">ATG</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Category</label>
                  <select
                    value={editForm.category}
                    onChange={(e) => setEditForm({ ...editForm, category: e.target.value })}
                    required
                    className="w-full bg-slate-800 border border-slate-700 rounded px-4 py-3 focus:outline-none focus:border-emerald-500"
                  >
                    <option value="">Select...</option>
                    {categories[editForm.market].map((cat) => (
                      <option key={cat.id} value={cat.id}>{cat.name}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">Event</label>
                <input
                  type="text"
                  value={editForm.event}
                  onChange={(e) => setEditForm({ ...editForm, event: e.target.value })}
                  required
                  className="w-full bg-slate-800 border border-slate-700 rounded px-4 py-3 focus:outline-none focus:border-emerald-500"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">Match date</label>
                <input
                  type="date"
                  value={editForm.match_date}
                  onChange={(e) => setEditForm({ ...editForm, match_date: e.target.value })}
                  required
                  className="w-full bg-slate-800 border border-slate-700 rounded px-4 py-3 focus:outline-none focus:border-emerald-500"
                />
              </div>
              {editingBet.status && ["won", "lost", "void"].includes(editingBet.status) && (
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Result</label>
                  <select
                    value={editForm.status}
                    onChange={(e) => setEditForm({ ...editForm, status: e.target.value as "won" | "lost" | "void" })}
                    className="w-full bg-slate-800 border border-slate-700 rounded px-4 py-3 focus:outline-none focus:border-emerald-500"
                  >
                    <option value="won">Won</option>
                    <option value="lost">Lost</option>
                    <option value="void">Void</option>
                  </select>
                </div>
              )}
              {(editForm.market === "props" || editForm.market === "tennis") && (
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Player</label>
                  <input
                    type="text"
                    value={editForm.player}
                    onChange={(e) => setEditForm({ ...editForm, player: e.target.value })}
                    className="w-full bg-slate-800 border border-slate-700 rounded px-4 py-3 focus:outline-none focus:border-emerald-500"
                  />
                </div>
              )}
              <div>
                <label className="block text-xs text-slate-500 mb-1">Selection</label>
                <input
                  type="text"
                  value={editForm.selection}
                  onChange={(e) => setEditForm({ ...editForm, selection: e.target.value })}
                  required
                  className="w-full bg-slate-800 border border-slate-700 rounded px-4 py-3 focus:outline-none focus:border-emerald-500"
                />
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Odds</label>
                  <input
                    type="number"
                    step="0.01"
                    min="1.01"
                    value={editForm.odds}
                    onChange={(e) => setEditForm({ ...editForm, odds: e.target.value })}
                    required
                    className="w-full bg-slate-800 border border-slate-700 rounded px-4 py-3 focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Bookmaker</label>
                  <select
                    value={editForm.bookmaker_id}
                    onChange={(e) => setEditForm({ ...editForm, bookmaker_id: e.target.value })}
                    required
                    className="w-full bg-slate-800 border border-slate-700 rounded px-4 py-3 focus:outline-none focus:border-emerald-500"
                  >
                    <option value="">Select...</option>
                    {bookmakers.map((bk) => (
                      <option key={bk.id} value={bk.id}>{bk.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">Stake (units)</label>
                  <input
                    type="number"
                    step="0.05"
                    min="0.1"
                    max="5"
                    value={editForm.stake}
                    onChange={(e) => setEditForm({ ...editForm, stake: e.target.value })}
                    required
                    className="w-full bg-slate-800 border border-slate-700 rounded px-4 py-3 focus:outline-none focus:border-emerald-500"
                  />
                </div>
              </div>
              <div>
                <label className="mb-1 block text-xs text-slate-500">Notes (optional)</label>
                <textarea
                  rows={3}
                  value={editForm.notes}
                  onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })}
                  className="w-full resize-y bg-slate-800 border border-slate-700 rounded px-4 py-3 focus:outline-none focus:border-emerald-500"
                />
              </div>
              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setEditingBet(null)}
                  className="flex-1 bg-slate-700 hover:bg-slate-600 text-slate-200 py-3 rounded font-medium transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="flex-1 bg-emerald-500 hover:bg-emerald-400 disabled:bg-slate-700 text-black font-medium py-3 rounded transition-colors"
                >
                  {loading ? "Saving..." : "Save"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
