"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import Footer from "@/components/Footer";
import PageHomeLink from "@/components/PageHomeLink";
import { track } from "@/lib/analytics";
import ReturnsLab, { type RecordSummary } from "@/components/calculator/ReturnsLab";
import KellyLab from "@/components/calculator/KellyLab";
import MarginLab from "@/components/calculator/MarginLab";
import ClvLab from "@/components/calculator/ClvLab";
import { summarizeCalculatorRecord, type RecordRow } from "@/lib/calculator/record";

type TabKey = "returns" | "kelly" | "margin" | "clv";

const TABS: Array<{ key: TabKey; label: string; hint: string }> = [
  { key: "returns", label: "Returns", hint: "Flat staking against our settled record" },
  { key: "kelly", label: "Kelly staking", hint: "Stake size, growth and drawdown" },
  { key: "margin", label: "Fair odds", hint: "Remove a bookmaker's margin" },
  { key: "clv", label: "Closing line", hint: "Measure a bet against the close" },
];

const CALCULATOR_FAQS = [
  {
    question: "What do these four calculators actually do?",
    answer:
      "Returns applies the strike rate and return on turnover from our settled record to a stake you choose, and simulates the range of results that edge produces. Kelly sizes a stake from your bankroll, the price and your probability, then shows what each fraction costs in drawdown. Fair odds removes a bookmaker's margin from a set of prices using three published methods. Closing line compares the price you took with a de-vigged closing price. All four are arithmetic on numbers you supply. None of them forecasts a result.",
  },
  {
    question: "Why is the returns curve a range rather than a line?",
    answer:
      "Because a line is not what happens. A record of 2,000 bets at a positive return is one ordering of wins and losses out of an enormous number of possible orderings, and the others include long losing runs that would have tested any bankroll. Simulating the same edge four hundred times shows the spread you would need to fund, and the deepest drawdown figure is usually more useful than the profit figure.",
  },
  {
    question: "Why does the tool ask how much of the edge I capture?",
    answer:
      "Published prices move. If a selection is posted at 2.10 and you take 1.95 an hour later, you have kept the position and given away most of the margin. Restricted accounts, one-bookmaker shopping and late entry all do the same thing. Setting capture below full is the realistic case for most people, but the appropriate setting depends on the prices actually obtained.",
  },
  {
    question: "Why do you use a tenth of Kelly on props and a quarter on tennis?",
    answer:
      "Kelly is optimal only if the probability you feed it is correct. Player prop probabilities carry far more estimation error than tennis match prices, because minutes, role and line movement all shift the distribution. The fraction is a haircut on confidence, not on ambition. Move the estimate error slider on the Kelly tab to see what a two point overestimate does to full Kelly and what it does to a quarter.",
  },
  {
    question: "Which margin removal method should I use?",
    answer:
      "Proportional is the quickest and the crudest. Shin uses a model of informed betting; in two-way markets it matches additive removal. Odds ratio uses a different adjustment. No method is universally best or guaranteed to sit between the others. On a balanced market they agree to within a few thousandths. On a heavy favourite they separate by more than most claimed edges, so always state which method produced a fair price.",
  },
  {
    question: "Does beating the closing line mean I am a winning bettor?",
    answer:
      "It means you bought the selection cheaper than the market finished pricing it, which is the best single-bet evidence available. It is only meaningful against a market that is sharp at the off. Beating a soft closing line repeatedly tells you the book was slow to move, which is a real edge but a fragile one, and usually the fastest route to a restricted account.",
  },
  {
    question: "What happens if the live results feed is down?",
    answer:
      "The Returns tab keeps the last available settled record if a refresh fails. If no current record has loaded, it uses the historical baseline and labels it clearly. The Kelly, Fair odds and Closing line tools use only the numbers you enter, so they work regardless.",
  },
] as const;

interface HowItWorksEntry {
  title: string;
  steps: string[];
}

const HOW_IT_WORKS: HowItWorksEntry[] = [
  {
    title: "Sizing a stake",
    steps: [
      "Start from the bank you would genuinely replace if it went, not the balance in one account.",
      "Price the bet first, then size it. A stake is a function of edge and uncertainty, never of confidence or of the last result.",
      "Cut the Kelly fraction until the worst one in twenty drawdown is a number you would keep betting through.",
    ],
  },
  {
    title: "Judging a price",
    steps: [
      "Remove the margin from a reference market before comparing anything to your own number.",
      "State the removal method alongside the fair price, because the methods disagree where it matters.",
      "Record the price you took and the price at the off. Over a season that record is worth more than the profit column.",
    ],
  },
];

function useRecordSummary(initialRecord: RecordSummary): RecordSummary {
  const [recordSummary, setRecordSummary] = useState<RecordSummary>(initialRecord);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch("/api/public-record?scope=calculator");
      const json = await res.json();
      if (!res.ok) throw new Error(json?.error || "Failed to load calculator record");

      if (!Array.isArray(json.stats) || json.stats.length === 0) throw new Error("Record totals are empty");
      const summary = summarizeCalculatorRecord(json.stats as RecordRow[]);
      setRecordSummary(summary);
      track("calculator_data_loaded", {
        roi_used: summary.roi,
        bets_count: summary.totalBets,
      });
    } catch {
      track("calculator_error", { type: "data_fetch" });
      setRecordSummary(previous => previous.source === "fallback" ? previous : { ...previous, source: "stale" });
    }
  }, []);

  useEffect(() => {
    track("calculator_view");
    const initialFetch = window.setTimeout(() => {
      void fetchData();
    }, 0);
    const handleFocus = () => void fetchData();
    const handleVisibility = () => {
      if (document.visibilityState === "visible") void fetchData();
    };
    window.addEventListener("focus", handleFocus);
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      window.clearTimeout(initialFetch);
      window.removeEventListener("focus", handleFocus);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [fetchData]);

  return recordSummary;
}

export default function CalculatorClient({ initialRecord }: { initialRecord: RecordSummary }) {
  const [activeTab, setActiveTab] = useState<TabKey>("returns");
  const record = useRecordSummary(initialRecord);

  const faqSchema = JSON.stringify({
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: CALCULATOR_FAQS.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: { "@type": "Answer", text: item.answer },
    })),
  });

  const selectTab = (key: TabKey) => {
    setActiveTab(key);
    track("calculator_tab", { tab: key });
  };

  return (
    <div className="calc-page">
      <script
        type="application/ld+json"
        suppressHydrationWarning
        dangerouslySetInnerHTML={{ __html: faqSchema }}
      />

      <div className="site-container">
        <header className="page-heading calc-heading">
          <PageHomeLink />
          <p className="site-eyebrow">Calculators and staking tools</p>
          <h1>The arithmetic, with the variance left in.</h1>
          <div className="page-intro">
            <p>
              Four tools that do the sums we run before a bet goes out: what a record is worth at your
              stake, how large that stake should be, what a price is worth once the margin comes off,
              and whether you bought it cheaper than the market closed. Calculations run in your browser. Stake and probability inputs are not saved.
            </p>
          </div>
          <dl className="calc-headline-stats">
            <div>
              <dt>Settled bets behind the returns tool</dt>
              <dd>{record.totalBets.toLocaleString("en-GB")}</dd>
            </div>
            <div>
              <dt>Return on turnover</dt>
              <dd className={record.roi >= 0 ? "gain" : "loss"}>
                {record.roi >= 0 ? "+" : ""}
                {record.roi.toFixed(1)}%
              </dd>
            </div>
            <div>
              <dt>Simulated runs per chart</dt>
              <dd>400</dd>
            </div>
          </dl>
        </header>

        <nav className="calc-tabs" aria-label="Calculator selection">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => selectTab(tab.key)}
              className={`calc-tab${activeTab === tab.key ? " is-active" : ""}`}
              aria-current={activeTab === tab.key ? "page" : undefined}
            >
              <strong>{tab.label}</strong>
              <span>{tab.hint}</span>
            </button>
          ))}
        </nav>

        <div className="calc-stage">
          {activeTab === "returns" ? <ReturnsLab record={record} /> : null}
          {activeTab === "kelly" ? <KellyLab /> : null}
          {activeTab === "margin" ? <MarginLab /> : null}
          {activeTab === "clv" ? <ClvLab /> : null}
        </div>

        <section className="calc-section">
          <p className="site-eyebrow">House rules</p>
          <h2>How we use these numbers</h2>
          <div className="calc-howto">
            {HOW_IT_WORKS.map((entry) => (
              <article key={entry.title} className="site-card">
                <h3>{entry.title}</h3>
                <ol>
                  {entry.steps.map((step, index) => (
                    <li key={step}>
                      <span className="site-step">{`0${index + 1}`}</span>
                      <p>{step}</p>
                    </li>
                  ))}
                </ol>
              </article>
            ))}
          </div>
        </section>

        <section className="calc-section">
          <p className="site-eyebrow">The point of fractional staking</p>
          <h2>Trade some growth for lower bankroll risk</h2>
          <div className="calc-prose">
            <p>
              Full Kelly is the stake that maximises long-run growth when your probability is exactly
              right. For small edges, half Kelly retains approximately 75% of optimal growth and quarter
              Kelly approximately 44%. Smaller stakes reduce volatility, but neither profits nor
              manageable drawdowns are guaranteed.
            </p>
            <p>
              The asymmetry matters more once you accept that no probability estimate is exact. Size
              too aggressively and expected log growth can become negative even when individual bets
              have positive expected value. The point where that happens depends on the inputs. That is why we run a tenth of Kelly on player
              props and a quarter on tennis, and why the Kelly tab lets you settle bets at a
              probability lower than the one you staked at.
            </p>
            <p>
              <Link href="/resources/kelly-criterion-sports-betting" className="site-text-link">
                The full Kelly guide
              </Link>
            </p>
          </div>
        </section>

        <section className="calc-section">
          <p className="site-eyebrow">Questions</p>
          <h2>What people ask about these tools</h2>
          <div className="calc-faq">
            {CALCULATOR_FAQS.map((item) => (
              <details key={item.question} className="site-disclosure">
                <summary>
                  {item.question}
                  <span aria-hidden="true">+</span>
                </summary>
                <p>{item.answer}</p>
              </details>
            ))}
          </div>
        </section>

        <p className="calc-compliance">
          <strong>Responsible gambling.</strong> These tools describe arithmetic, not outcomes. Past
          performance does not guarantee future results, and only money you can afford to lose should
          ever reach a betting account.{" "}
          <a href="https://www.begambleaware.org" rel="noopener noreferrer">
            BeGambleAware
          </a>{" "}
          and{" "}
          <a href="https://www.gamcare.org.uk" rel="noopener noreferrer">
            GamCare
          </a>{" "}
          are there if betting has stopped being a choice.
        </p>
      </div>

      <Footer />
    </div>
  );
}
