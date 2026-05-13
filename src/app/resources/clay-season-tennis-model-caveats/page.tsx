import type { Metadata } from "next";
import Link from "next/link";
import ResourceArticlePage from "@/components/ResourceArticlePage";
import { BASE_URL } from "@/lib/config";

const PATH = "/resources/clay-season-tennis-model-caveats";
const TITLE = "Why our ATP model is conservative on clay";
const DESCRIPTION =
  "A lab note on clay volatility, player fitness, calibration risk, and why the model treats clay-court betting edges more carefully than hard courts.";

export const metadata: Metadata = {
  title: `${TITLE} | Il Margine Lab Notes`,
  description: DESCRIPTION,
  alternates: {
    canonical: `${BASE_URL}${PATH}`,
  },
  robots: "index, follow",
};

const TOC = [
  { id: "why-clay-is-different", label: "Why clay is different" },
  { id: "what-we-watch", label: "What we watch" },
  { id: "model-response", label: "Model response" },
  { id: "where-it-goes-next", label: "Where it goes next" },
];

export default function ClaySeasonTennisModelCaveatsPage() {
  return (
    <ResourceArticlePage
      eyebrow="Lab note - tennis"
      title={TITLE}
      description={DESCRIPTION}
      canonicalPath={PATH}
      datePublished="2026-05-13"
      toc={TOC}
    >
      <section id="why-clay-is-different">
        <h2 className="mb-6 text-2xl font-semibold text-slate-100 sm:text-3xl">
          Why clay is different
        </h2>
        <p>
          Clay is the surface where our ATP model deserves the least ego. Serve advantage is softer,
          rallies stretch longer, and match outcomes lean harder into physical condition than a simple
          hard-court form line suggests. That does not make clay unmodellable. It does mean the model
          needs wider error bars and less confidence in marginal edges.
        </p>
        <p>
          The biggest issue is not that clay is random. It is that the market knows clay is awkward
          too. When both the model and the market are trying to price form, fatigue, surface history,
          and player tolerance at the same time, small edges can evaporate quickly.
        </p>
      </section>

      <section id="what-we-watch">
        <h2 className="mb-6 mt-12 text-2xl font-semibold text-slate-100 sm:text-3xl">
          What we watch
        </h2>
        <p>
          The first layer is calibration. If the model says a player should win 60 percent of the
          time on clay, the historical bucket needs to behave like a 60 percent bucket. If that bucket
          settles closer to 53 or 54 percent, the number is not value. It is overconfidence with a
          nicer label.
        </p>
        <p>
          The second layer is score distribution. Games handicaps are sensitive to how a favourite
          wins, not just whether they win. Clay can produce more long sets, more breaks back, and more
          three-set paths. A player can be the right moneyline side and still be the wrong handicap
          side.
        </p>
        <p>
          The third layer is timing. Early clay swings are especially dangerous because public form is
          often stale. A player can arrive with strong hard-court numbers and still need two matches
          to look comfortable sliding, defending, and constructing points on clay.
        </p>
      </section>

      <section id="model-response">
        <h2 className="mb-6 mt-12 text-2xl font-semibold text-slate-100 sm:text-3xl">
          Model response
        </h2>
        <p>
          For now, clay signals stay more conservative than hard-court signals. We are more willing
          to block low-margin moneyline spots, keep clay-only lanes in research, and separate favourite
          handicap tests from dog handicap tests instead of treating them as the same market.
        </p>
        <p>
          That is why a clay card can look quieter than a hard-court card on{" "}
          <Link href="/tennis-tips" className="text-emerald-300 hover:text-emerald-200">
            tennis tips
          </Link>
          . Quiet is not a bug. If the model is not earning enough separation from the reference
          market, the right action is to pass.
        </p>
      </section>

      <section id="where-it-goes-next">
        <h2 className="mb-6 mt-12 text-2xl font-semibold text-slate-100 sm:text-3xl">
          Where it goes next
        </h2>
        <p>
          The next clay work is not a bigger hype filter. It is better calibration: clay-only spread
          fits, stricter probability buckets, and clearer reporting on where the model disagrees with
          the closing market. If the research lane earns it, the signal can graduate. If it does not,
          it stays off the public board.
        </p>
        <p>
          The aim is simple: fewer clay bets, better defended. A model does not need to have an
          opinion on every match to be useful.
        </p>
      </section>
    </ResourceArticlePage>
  );
}
