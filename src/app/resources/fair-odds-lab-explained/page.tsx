import type { Metadata } from "next";
import Link from "next/link";
import ResourceArticlePage from "@/components/ResourceArticlePage";
import { BASE_URL } from "@/lib/config";

const PATH = "/resources/fair-odds-lab-explained";
const TITLE = "What the Fair Odds Lab shows, and what it does not";
const DESCRIPTION =
  "How to read Il Margine fair prices, reference odds, price gaps, and model flags without confusing research signals for guaranteed betting picks.";

export const metadata: Metadata = {
  title: `${TITLE} | Il Margine Lab Notes`,
  description: DESCRIPTION,
  alternates: {
    canonical: `${BASE_URL}${PATH}`,
  },
  robots: "index, follow",
};

const TOC = [
  { id: "fair-price", label: "Fair price" },
  { id: "reference-price", label: "Reference price" },
  { id: "price-gap", label: "Price gap" },
  { id: "what-it-is-not", label: "What it is not" },
];

export default function FairOddsLabExplainedPage() {
  return (
    <ResourceArticlePage
      eyebrow="Lab note - method"
      title={TITLE}
      description={DESCRIPTION}
      canonicalPath={PATH}
      datePublished="2026-05-13"
      toc={TOC}
    >
      <section id="fair-price">
        <h2 className="mb-6 text-2xl font-semibold text-slate-100 sm:text-3xl">
          Fair price
        </h2>
        <p>
          The{" "}
          <Link href="/fair-odds-lab" className="text-emerald-300 hover:text-emerald-200">
            Fair Odds Lab
          </Link>{" "}
          starts with a model price. That price is our estimate of what the odds would be if the
          market had no margin and the player probability matched our inputs. It is not a promise
          that the player will score or win. It is the price at which the model would stop calling
          the selection value.
        </p>
        <p>
          If the model fair price is 2.20, the implied probability is around 45.5 percent. If the
          available reference price is longer than that, the model sees a possible gap. If the
          available price is shorter, there is no value signal.
        </p>
      </section>

      <section id="reference-price">
        <h2 className="mb-6 mt-12 text-2xl font-semibold text-slate-100 sm:text-3xl">
          Reference price
        </h2>
        <p>
          The Lab uses a single bookmaker reference so signals stay comparable. That reference is not
          a best-price claim. It is simply the market number used to compare against the model's fair
          price at the moment the board updates.
        </p>
        <p>
          This matters because "best price" language can be misleading. A better price may exist
          somewhere else, or the reference price may move after the Lab updates. The useful question is
          narrower: does the model materially disagree with a consistent reference market?
        </p>
      </section>

      <section id="price-gap">
        <h2 className="mb-6 mt-12 text-2xl font-semibold text-slate-100 sm:text-3xl">
          Price gap
        </h2>
        <p>
          The price gap is shown in percentage points. If the model gives a player a 45.7 percent
          scoring chance and the reference price implies 31.2 percent, the gap is 14.5 percentage
          points. That does not mean the bet has a 14.5 percent ROI. It means the model probability is
          14.5 points higher than the market-implied probability.
        </p>
        <p>
          Big gaps are useful, but they are not automatically better. A very large gap can mean the
          model has found something real. It can also mean team news, minutes risk, or market movement
          has not been handled properly. That is why the Lab favours visible caveats over "lock" type
          language.
        </p>
      </section>

      <section id="what-it-is-not">
        <h2 className="mb-6 mt-12 text-2xl font-semibold text-slate-100 sm:text-3xl">
          What it is not
        </h2>
        <p>
          The Lab is not an official track record, not a guarantee, and not a place for accumulator
          hype. It is a research surface: current model prices, current reference prices, and recent
          examples where the model flagged value and the event later happened.
        </p>
        <p>
          The settled record belongs on{" "}
          <Link href="/track-record" className="text-emerald-300 hover:text-emerald-200">
            the track record page
          </Link>
          . The Lab belongs earlier in the process: before the result, while the disagreement between
          model and market is still visible.
        </p>
      </section>
    </ResourceArticlePage>
  );
}
