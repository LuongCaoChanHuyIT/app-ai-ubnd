export interface SessionManager {
  getOrInitSessionId(): string;
  rotateSessionId(): string;
  getActiveActorEmail(): string;
  setActiveActorEmail(email: string): void;
}

function generateId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `ubnd-${crypto.randomUUID().slice(0, 12)}`;
  }
  return `ubnd-${Math.random().toString(36).slice(2, 10)}-${Date.now().toString(36)}`;
}

export function createMemorySessionManager(
  defaultEmail = "tsh.co@tshorg.vn",
): SessionManager {
  let currentSessionId = "";
  let currentActorEmail = defaultEmail;

  return {
    getOrInitSessionId() {
      if (!currentSessionId) {
        currentSessionId = generateId();
      }
      return currentSessionId;
    },
    rotateSessionId() {
      currentSessionId = generateId();
      return currentSessionId;
    },
    getActiveActorEmail() {
      return currentActorEmail;
    },
    setActiveActorEmail(email: string) {
      currentActorEmail = email.trim() || defaultEmail;
    },
  };
}

const SESSION_KEY = "ubnd_ai_session_id";
const ACTOR_KEY = "ubnd_ai_actor_email";
const fallbackMgr = createMemorySessionManager();

export function getOrInitSessionId(): string {
  if (typeof window === "undefined") {
    return fallbackMgr.getOrInitSessionId();
  }
  let existing = window.sessionStorage.getItem(SESSION_KEY);
  if (!existing) {
    existing = generateId();
    window.sessionStorage.setItem(SESSION_KEY, existing);
  }
  return existing;
}

export function rotateSessionId(): string {
  if (typeof window === "undefined") {
    return fallbackMgr.rotateSessionId();
  }
  const next = generateId();
  window.sessionStorage.setItem(SESSION_KEY, next);
  window.dispatchEvent(new CustomEvent("ubnd-session-changed", { detail: next }));
  return next;
}

export function getActiveActorEmail(): string {
  if (typeof window === "undefined") {
    return fallbackMgr.getActiveActorEmail();
  }
  return window.localStorage.getItem(ACTOR_KEY) || "tsh.co@tshorg.vn";
}

export function setActiveActorEmail(email: string): void {
  const cleaned = email.trim() || "tsh.co@tshorg.vn";
  if (typeof window === "undefined") {
    fallbackMgr.setActiveActorEmail(cleaned);
    return;
  }
  window.localStorage.setItem(ACTOR_KEY, cleaned);
  window.dispatchEvent(new CustomEvent("ubnd-actor-changed", { detail: cleaned }));
}

