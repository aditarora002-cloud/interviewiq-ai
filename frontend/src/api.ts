const BASE = ((import.meta as ImportMeta & { env: { VITE_API_URL?: string } }).env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const TOKEN_KEY = 'interviewiq_auth_token';
export function getAuthToken() { return localStorage.getItem(TOKEN_KEY); }
export function setAuthToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}
async function req(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  const token = getAuthToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const r = await fetch(BASE + path, { ...init, headers });
  if (!r.ok) {
    let msg = `Request failed (${r.status})`;
    try {
      const detail = (await r.json()).detail;
      msg = typeof detail === 'string' ? detail : JSON.stringify(detail);
    } catch { /* keep status message */ }
    if (r.status === 401 && !path.startsWith('/api/auth/login') && !path.startsWith('/api/auth/register')) {
      setAuthToken(null);
      window.dispatchEvent(new Event('interviewiq:session-expired'));
    }
    throw new Error(msg);
  }
  return r;
}
export async function getJSON(path: string) { return (await req(path)).json(); }
export async function postJSON(path: string, body: unknown) {
  return (await req(path, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) })).json();
}
export async function deleteJSON(path: string) { return (await req(path, {method: 'DELETE'})).json(); }
export async function uploadResume(file: File, target?: {role:string; company:string; job_description:string}) {
  const f = new FormData(); f.append('file', file);
  if (target) { f.append('role', target.role); f.append('company', target.company); f.append('job_description', target.job_description); }
  return (await req('/api/resume/analyze', {method: 'POST', body: f})).json();
}
export async function downloadReport(id: string) {
  const r = await req(`/api/interviews/${encodeURIComponent(id)}/report`);
  const url = URL.createObjectURL(await r.blob());
  const a = document.createElement('a'); a.href = url; a.download = `interviewiq-${id.slice(0,8)}.pdf`; a.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function putJSON(path: string, body: unknown) {
  return (await req(path, { method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) })).json();
}
