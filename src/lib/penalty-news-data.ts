import "server-only";
import news from "@/data/penalty-news.json";
import type { PenaltyArticle } from "./penalty-news";
import { distinctNewsTitle } from "./penalty-news";

// Evidence and provider provenance stay in the saved audit input, not browser props.
// The presentation helpers deliberately do not import the full archive.
const articles: PenaltyArticle[] = news.articles.map(article => {
  const publicArticle: Partial<typeof article> = { ...article };
  delete publicArticle.sourceUrl;
  delete publicArticle.sourceHash;
  delete publicArticle.incident;
  return { ...publicArticle, title: distinctNewsTitle(article as PenaltyArticle, news.articles as PenaltyArticle[]) } as PenaltyArticle;
});
export const penaltyNews = {
  schemaVersion: news.schemaVersion, generatedAt: news.generatedAt,
  coverageStart: news.coverageStart, checkedThrough: news.checkedThrough,
  matchesChecked: news.matchesChecked, articles,
};
