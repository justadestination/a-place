// Share intents. Uses the Web Share API where the device has it, otherwise
// returns plain intent URLs the ShareButton lists as links.

export function shareUrl(path = location.pathname + location.search) {
  return new URL(path, location.origin).href;
}

export function intents({ title, text, url }) {
  const t = encodeURIComponent(text || title || "");
  const u = encodeURIComponent(url);
  return [
    { id: "x", label: "Post on X", href: `https://twitter.com/intent/tweet?text=${t}&url=${u}` },
    { id: "bluesky", label: "Post on Bluesky", href: `https://bsky.app/intent/compose?text=${encodeURIComponent(`${text || title || ""} ${url}`)}` },
    { id: "facebook", label: "Share on Facebook", href: `https://www.facebook.com/sharer/sharer.php?u=${u}` },
    { id: "email", label: "Send by email", href: `mailto:?subject=${encodeURIComponent(title || "")}&body=${encodeURIComponent(`${text ? text + "\n\n" : ""}${url}`)}` },
  ];
}

export const canNativeShare = () => typeof navigator !== "undefined" && typeof navigator.share === "function";

/** Native share sheet. Resolves true if shared, false if unavailable or cancelled. */
export async function nativeShare(data) {
  if (!canNativeShare()) return false;
  try { await navigator.share(data); return true; } catch { return false; }
}

export async function copy(text) {
  try { await navigator.clipboard.writeText(text); return true; } catch { /* fall through */ }
  const area = document.createElement("textarea");
  area.value = text; area.setAttribute("readonly", ""); area.style.position = "fixed"; area.style.opacity = "0";
  document.body.append(area); area.select();
  let ok = false;
  try { ok = document.execCommand("copy"); } catch { ok = false; }
  area.remove();
  return ok;
}
