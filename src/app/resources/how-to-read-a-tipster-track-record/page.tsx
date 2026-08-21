import type { Metadata } from "next";
import Link from "next/link";
import ResourceArticlePage from "@/components/ResourceArticlePage";
import { BASE_URL } from "@/lib/config";

const PATH = "/resources/how-to-read-a-tipster-track-record";
const TITLE = "How to Verify a Tipster Track Record: ROI, CLV and Drawdown";
const DESCRIPTION =
  "A practical checklist for verifying a tipster record using timestamps, sample size, ROI, closing-line value, drawdown and visible losing bets.";

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  alternates: {
    canonical: `${BASE_URL}${PATH}`,
  },
  robots: "index, follow",
  openGraph: { title: TITLE, description: DESCRIPTION, url: `${BASE_URL}${PATH}`, type: "article", images: [`${BASE_URL}/og-social-20260629.png`] },
  twitter: { card: "summary_large_image", title: TITLE, description: DESCRIPTION, images: [`${BASE_URL}/og-social-20260629.png`] },
};

const TOC = [
  { id: "timestamps", label: "Timestamps" },
  { id: "losses", label: "Visible losses" },
  { id: "sample-size", label: "Sample size" },
  { id: "clv-and-drawdown", label: "CLV and drawdown" },
];

export default function HowToReadATipsterTrackRecordPage() {
  return (
    <ResourceArticlePage
      eyebrow="Lab note - method"
      title={TITLE}
      description={DESCRIPTION}
      canonicalPath={PATH}
      datePublished="2026-05-13"
      dateModified="2026-08-21"
      toc={TOC}
    >
      <section id="timestamps">
        <h2 className="mb-6 text-2xl font-semibold text-slate-100 sm:text-3xl">
          Timestamps first
        </h2>
        <p>
          The first question for any betting record is simple: was the selection visible before the
          event started? A record that only appears after results settle is not much evidence. It may
          be accurate, but the reader cannot audit the most important part.
        </p>
        <p>
          A useful record has timestamps, prices, stakes, and settled results. The timestamp matters
          because it proves the selection existed while the market was still open. Without it, a
          strong ROI number is just a claim.
        </p>
      </section>

      <section id="losses">
        <h2 className="mb-6 mt-12 text-2xl font-semibold text-slate-100 sm:text-3xl">
          Losses need to be visible
        </h2>
        <p>
          Losing bets are not a flaw in a real record. They are part of the record. A service that
          hides losing weeks, deletes posts, or only screenshots winning slips is telling you more
          about its process than the wins ever could.
        </p>
        <p>
          This is especially important for model-led betting. The right question is not whether the
          latest signal won. The right question is whether the same process, applied repeatedly, beats
          the price over enough attempts.
        </p>
      </section>

      <section id="sample-size">
        <h2 className="mb-6 mt-12 text-2xl font-semibold text-slate-100 sm:text-3xl">
          Sample size changes everything
        </h2>
        <p>
          Twenty bets can look spectacular by accident. Fifty bets can still flatter a bad process.
          Once a record reaches hundreds of settled selections, the numbers become more useful, but
          they still need context: market type, average odds, staking method, and whether the bets
          came from the same model logic.
        </p>
        <p>
          That is why the{" "}
          <Link href="/track-record" className="text-emerald-300 hover:text-emerald-200">
            Il Margine track record
          </Link>{" "}
          separates market history rather than collapsing everything into one headline. Tennis,
          player props, and goalscorer research do not have the same volatility profile.
        </p>
      </section>

      <section id="clv-and-drawdown">
        <h2 className="mb-6 mt-12 text-2xl font-semibold text-slate-100 sm:text-3xl">
          CLV and drawdown
        </h2>
        <p>
          Closing-line value is the cleanest process check. If a selection regularly beats the
          closing price, the process is probably finding useful numbers even when short-term results
          are ugly. If it regularly loses to the closing price, a winning run may just be variance.
        </p>
        <p>
          Drawdown matters too. Every betting strategy has losing stretches. The serious question is
          whether those losing stretches are survivable at the stated staking level. A record that
          shows ROI without drawdown hides the part users actually have to live through.
        </p>
        <p>
          Past performance still does not guarantee future returns. The value of a track record is not
          certainty. It is transparency: enough evidence to judge whether the process deserves
          attention.
        </p>
      </section>
    </ResourceArticlePage>
  );
}
