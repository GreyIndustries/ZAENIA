/**
 * What a build request shows (Claude 2026-11-11). Coding tools sometimes return their private working notes
 * before the answer ("Wait, the user also mentioned… **ANSWER** …"). ZAE keeps private reasoning out of the UI:
 * only the final answer is shown. Tool cache/history files are hidden from the displayed file list
 * (display only; what was committed is unchanged).
 */
const MARKERS = [/\*\*\s*answer\s*\*\*\s*:?/gi, /^#{1,4}\s*(?:final\s+)?answer\s*:?\s*$/gim, /^\s*(?:final\s+)?answer\s*:\s*/gim, /<\/think>/gi];
export function finalAnswer(text: string | undefined | null): string {
  if (!text) return "";
  let out = text.replace(/<think>[\s\S]*?<\/think>/gi, "");
  let cut = -1, length = 0;
  for (const marker of MARKERS) { marker.lastIndex = 0; for (const match of out.matchAll(marker)) if (match.index !== undefined && match.index >= cut) { cut = match.index; length = match[0].length; } }
  if (cut >= 0) out = out.slice(cut + length);
  return out.replace(/^[\s\-–—=*_]+/, "").trim();
}
const HIDDEN = [/(^|[\\/])\.aider[^\\/]*($|[\\/])/i, /(^|[\\/])\.aider\.tags\.cache/i, /(^|[\\/])__pycache__([\\/]|$)/i, /\.pyc$/i];
export function displayFiles(files: string[] | undefined | null): string[] {
  return (files ?? []).filter(file => !HIDDEN.some(rule => rule.test(file)));
}
