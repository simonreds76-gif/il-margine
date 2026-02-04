"use client";

import { useState, useEffect } from "react";
import { supabase, Bet, Bookmaker } from "@/lib/supabase";

// Hardcoded password (since env vars can be tricky with Vercel)
const ADMIN_PASSWORD = "Absolut2015!";

export default function AdminPanel() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [activeTab, setActiveTab] = useState<"add" | "pending" | "recent">("add");
  const [bookmakers, setBookmakers] = useState<Bookmaker[]>([]);
  const [pendingBets, setPendingBets] = useState<Bet[]>([]);
  const [recentBets, setRecentBets] = useState<Bet[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

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
    notes: "",
  });

  const categories = {
    props: [
      { id: "pl", name: "Premier League" },
      { id: "seriea", name: "Serie A" },
      { id: "ucl", name: "Champions League" },
      { id: "other", name: "Other" },
    ],
    tennis: [
      { id: "atp", name: "ATP Tour" },
      { id: "challenger", name: "Challenger" },
      { id: "ausopen", name: "Australian Open" },
      { id: "other", name: "Other" },
    ],
    betbuilders: [
      { id: "pl", name: "Premier League" },
      { id: "seriea", name: "Serie A" },
      { id: "other", name: "Other" },
    ],
    atg: [
      { id: "pl", name: "Premier League" },
      { id: "seriea", name: "Serie A" },
      { id: "other", name: "Other" },
    ],
  };

  // Check password - hardcoded for reliability
  const handleLogin = () => {
    if (password === ADMIN_PASSWORD) {
      setIsLoggedIn(true);
      localStorage.setItem("admin_logged_in", "true");
    } else {
      setMessage({ type: "error", text: "Wrong password" });
    }
  };

  // Check if already logged in
  useEffect(() => {
    if (localStorage.getItem("admin_logged_in") === "true") {
      setIsLoggedIn(true);
    }
  }, []);

  // Fetch bookmakers
  useEffect(() => {
    if (isLoggedIn) {
      fetchBookmakers();
      fetchPendingBets();
      fetchRecentBets();
    }
  }, [isLoggedIn]);

  const fetchBookmakers = async () => {
    const { data, error } = await supabase
      .from("bookmakers")
      .select("*")
      .eq("active", true)
      .order("name");
    if (data) setBookmakers(data);
    if (error) console.log("Bookmakers error:", error);
  };

  const fetchPendingBets = async () => {
    const { data, error } = await supabase
      .from("bets")
      .select("*, bookmaker:bookmakers(*)")
      .eq("status", "pending")
      .order("posted_at", { ascending: false });
    if (data) setPendingBets(data);
    if (error) console.log("Pending bets error:", error);
  };

  const fetchRecentBets = async () => {
    const { data, error } = await supabase
      .from("bets")
      .select("*, bookmaker:bookmakers(*)")
      .in("status", ["won", "lost", "void"])
      .order("settled_at", { ascending: false })
      .limit(50);
    if (data) {
      console.log("Recent bets fetched:", data);
      setRecentBets(data);
    }
    if (error) console.log("Recent bets error:", error);
  };

  // Add new bet
  const handleAddBet = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setMessage(null);

    const { error } = await supabase.from("bets").insert([
      {
        market: form.market,
        category: form.category,
        event: form.event,
        player: form.player || null,
        selection: form.selection,
        odds: parseFloat(form.odds),
        bookmaker_id: parseInt(form.bookmaker_id),
        stake: parseFloat(form.stake),
        notes: form.notes || null,
      },
    ]);

    setLoading(false);

    if (error) {
      setMessage({ type: "error", text: error.message });
    } else {
      setMessage({ type: "success", text: "Bet added successfully!" });
      setForm({
        ...form,
        event: "",
        player: "",
        selection: "",
        odds: "",
        notes: "",
      });
      fetchPendingBets();
    }
  };

  // Settle bet
  const handleSettle = async (betId: number, status: "won" | "lost" | "void") => {
    setLoading(true);
    setMessage(null);
    
    // First, fetch the bet to get odds and stake for profit calculation
    const { data: bet, error: fetchError } = await supabase
      .from("bets")
      .select("odds, stake")
      .eq("id", betId)
      .single();

    if (fetchError || !bet) {
      setLoading(false);
      setMessage({ type: "error", text: "Failed to fetch bet details" });
      return;
    }

    // Calculate profit/loss based on status
    let profitLoss: number;
    if (status === "won") {
      // Profit = (odds * stake) - stake
      profitLoss = Number(bet.odds) * Number(bet.stake) - Number(bet.stake);
    } else if (status === "lost") {
      // Loss = -stake
      profitLoss = -Number(bet.stake);
    } else {
      // Void = 0
      profitLoss = 0;
    }

    // Update bet with status, profit_loss, and settled_at timestamp
    const { error } = await supabase
      .from("bets")
      .update({ 
        status,
        profit_loss: profitLoss,
        settled_at: new Date().toISOString()
      })
      .eq("id", betId);

    setLoading(false);

    if (error) {
      setMessage({ type: "error", text: error.message });
    } else {
      setMessage({ type: "success", text: `Bet marked as ${status}. P/L: ${profitLoss > 0 ? "+" : ""}${profitLoss.toFixed(2)}u` });
      // Refresh both lists
      await fetchPendingBets();
      await fetchRecentBets();
    }
  };

  // Delete bet
  const handleDelete = async (betId: number) => {
    if (!confirm("Are you sure you want to delete this bet?")) return;

    const { error } = await supabase.from("bets").delete().eq("id", betId);

    if (error) {
      setMessage({ type: "error", text: error.message });
    } else {
      setMessage({ type: "success", text: "Bet deleted" });
      fetchPendingBets();
      fetchRecentBets();
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
            onClick={() => {
              localStorage.removeItem("admin_logged_in");
              setIsLoggedIn(false);
            }}
            className="text-sm text-slate-400 hover:text-slate-100"
          >
            Logout
          </button>
        </div>
      </header>

      {/* Tabs */}
      <div className="border-b border-slate-800">
        <div className="max-w-4xl mx-auto flex">
          {[
            { id: "add", label: "Add Bet" },
            { id: "pending", label: `Pending (${pendingBets.length})` },
            { id: "recent", label: `Recent (${recentBets.length})` },
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
              {tab.label}
            </button>
          ))}
        </div>
      </div>

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

            {/* Player (optional) */}
            {form.market === "props" && (
              <div>
                <label className="block text-xs text-slate-500 mb-1">Player</label>
                <input
                  type="text"
                  placeholder="e.g. Saka"
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
                placeholder="e.g. Over 2.5 Shots"
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
                  min="0.05"
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
              <label className="block text-xs text-slate-500 mb-1">Notes (optional)</label>
              <input
                type="text"
                placeholder="Any notes..."
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                className="w-full bg-slate-800 border border-slate-700 rounded px-4 py-3 focus:outline-none focus:border-emerald-500"
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
                        {bet.odds}
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
                  <div className="flex gap-2">
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
                        @ {bet.odds} • {bet.stake}u
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
    </div>
  );
}
