/* Aadyon Assist — shared front-end helpers used by every dashboard page. */
function el(h){ const t=document.createElement('template'); t.innerHTML=h.trim(); return t.content.firstChild; }
function esc(s){ return (s==null?'':String(s)).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function money(n){ return n==null ? '—' : '$'+Number(n).toLocaleString('en-US',{maximumFractionDigits:0}); }
function money2(n){ return n==null ? '—' : '$'+Number(n).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}); }
function num(n){ return n==null ? '—' : Number(n).toLocaleString('en-US'); }
// Back-compat alias: pages historically used `$` as the element-from-HTML helper.
const $ = el;

// Consistent top-right nav across pages. Any <nav data-nav> is filled with the
// full link set, with the current page marked active. Keeps every page in sync.
const NAV_LINKS = [
  ['/', 'Digital Me'], ['/tracker', 'Tracker'], ['/agency', 'Agency'],
  ['/data', 'Data'], ['/accounts', 'Accounts'], ['/docs', 'API'],
];
function renderNav(){
  const here = (location.pathname.replace(/\/+$/, '') || '/');
  const html = NAV_LINKS.map(([href, label]) => {
    const ext = href === '/docs' ? ' target="_blank"' : '';
    const active = (href === '/' ? here === '/' : here === href) ? ' class="active"' : '';
    return `<a href="${href}"${ext}${active}>${label}</a>`;
  }).join('');
  document.querySelectorAll('[data-nav]').forEach(n => { n.innerHTML = html; });
}
document.addEventListener('DOMContentLoaded', renderNav);
