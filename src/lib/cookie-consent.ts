export const CONSENT_KEY = "ilmargine_cookie_consent";
export const CONSENT_EVENT = "ilmargine-consent-change";
export type ConsentState = "accepted" | "rejected" | "pending";
type ConsentChoice = Exclude<ConsentState, "pending">;

// Only used if the browser refuses persistence. Never assume acceptance.
let sessionChoice: ConsentChoice | null = null;

export function readConsentSnapshot(): ConsentState {
  if (typeof window === "undefined") return "pending";
  if (sessionChoice) return sessionChoice;
  try {
    const stored = window.localStorage.getItem(CONSENT_KEY);
    return stored === "1" ? "accepted" : stored === "0" ? "rejected" : "pending";
  } catch {
    return "pending";
  }
}

export function readServerConsentSnapshot(): ConsentState {
  return "pending";
}

function syncConsentAttribute() {
  const consent = readConsentSnapshot();
  if (consent === "pending") document.documentElement.removeAttribute("data-cookie-consent");
  else document.documentElement.setAttribute("data-cookie-consent", consent);
}

export function saveConsent(choice: ConsentChoice) {
  try {
    window.localStorage.setItem(CONSENT_KEY, choice === "accepted" ? "1" : "0");
    sessionChoice = null;
  } catch {
    sessionChoice = choice;
  }
  syncConsentAttribute();
  window.dispatchEvent(new Event(CONSENT_EVENT));
}

export function subscribeToConsent(onStoreChange: () => void) {
  if (typeof window === "undefined") return () => {};
  const onChange = () => {
    syncConsentAttribute();
    onStoreChange();
  };
  const onStorage = (event: StorageEvent) => {
    if (event.key !== null && event.key !== CONSENT_KEY) return;
    sessionChoice = null;
    onChange();
  };
  syncConsentAttribute();
  window.addEventListener("storage", onStorage);
  window.addEventListener(CONSENT_EVENT, onChange);
  return () => {
    window.removeEventListener("storage", onStorage);
    window.removeEventListener(CONSENT_EVENT, onChange);
  };
}

// Hide an already-decided banner before first paint. Never start analytics here.
export const CONSENT_PREPAINT_SCRIPT = `try{var c=localStorage.getItem('${CONSENT_KEY}');if(c==='1'||c==='0')document.documentElement.setAttribute('data-cookie-consent',c==='1'?'accepted':'rejected')}catch{}`;
