import html as _html
import httpx
import json as _json
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import select

router = APIRouter()

_REMNAWAVE = "http://127.0.0.1:3000"

_RU_MONTHS = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]

_PAGE_TEMPLATE = """\
<!doctype html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DS-VPN — Подписка</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Ctext y='26' font-size='26' font-weight='900' font-family='Arial,sans-serif' fill='%233b82f6'%3EDS%3C/text%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#0d1117;--card:#161c27;--card2:#111623;
  --brd:rgba(255,255,255,.07);--brd-h:rgba(59,130,246,.4);
  --txt:#e2e8f0;--muted:#64748b;
  --blue:#3b82f6;--blue2:#60a5fa;
  --bg-btn:rgba(59,130,246,.1);
  --green:#22c55e;--amber:#f59e0b;
}

*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
  background-color:var(--bg);color:var(--txt);min-height:100vh;
  padding:20px 16px;overflow-x:hidden;
  background-image:radial-gradient(rgba(59,130,246,.07) 1px,transparent 1px);
  background-size:28px 28px}
body::before{content:'';position:fixed;top:0;left:50%;transform:translateX(-50%);
  width:110%;max-width:800px;height:480px;
  background:radial-gradient(ellipse at 50% -10%,rgba(37,99,235,.11) 0%,transparent 62%);
  pointer-events:none;z-index:0}
.wrap{max-width:640px;margin:0 auto;padding:4px 0 56px;
  position:relative;z-index:1;
  animation:fu .5s ease both}
@keyframes fu{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:translateY(0)}}

/* ── HEADER ── */
.hdr{display:flex;justify-content:space-between;align-items:center;
  margin-bottom:28px;padding-bottom:18px;border-bottom:1px solid var(--brd)}
.logo{display:flex;align-items:baseline;gap:0;line-height:1;cursor:default}
.logo-ds{font-size:28px;font-weight:900;letter-spacing:-1.5px;color:#4f90ff;
  text-shadow:0 0 18px rgba(59,130,246,.85),0 0 36px rgba(59,130,246,.4),0 0 60px rgba(59,130,246,.15)}
.logo-vpn{font-size:20px;font-weight:700;letter-spacing:-.5px;
  color:rgba(96,165,250,.6);margin-left:1px}
.hdr-btns{display:flex;gap:8px}
.hdr-btn{background:var(--card);border:1px solid var(--brd);border-radius:10px;
  width:38px;height:38px;display:flex;align-items:center;justify-content:center;
  cursor:pointer;color:var(--muted);transition:all .2s;text-decoration:none}
.hdr-btn:hover{color:var(--blue2);border-color:var(--brd-h)}

/* ── USER CARD ── */
.ucard{background:var(--card);border:1px solid var(--brd);border-radius:16px;
  padding:22px 22px 20px;margin-bottom:20px;
  animation:fu .5s .06s ease both}
.utop{display:flex;align-items:center;gap:12px;margin-bottom:4px}
.uav{width:36px;height:36px;border-radius:50%;
  background:rgba(34,197,94,.18);border:1px solid rgba(34,197,94,.32);
  display:flex;align-items:center;justify-content:center;color:var(--green);flex-shrink:0}
.uname{font-size:16px;font-weight:700}
.usub{font-size:12px;color:var(--muted);margin:4px 0 18px 48px}
.ugrid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.ucell{background:var(--card2);border:1px solid var(--brd);border-radius:10px;padding:12px 14px}
.ulabel{font-size:10px;text-transform:uppercase;letter-spacing:.7px;color:var(--muted);
  display:flex;align-items:center;gap:5px;margin-bottom:7px}
.uval{font-size:14px;font-weight:700}
.ig{color:var(--green)}.io{color:var(--amber)}
.s-act{color:var(--green)}.s-ina{color:#ef4444}

/* ── ACTIVITY ── */
.acard{background:var(--card);border:1px solid var(--brd);border-radius:16px;
  padding:18px 20px;margin-bottom:20px;animation:fu .5s .1s ease both}
.acard-hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}
.acard-title{font-size:15px;font-weight:700}
.abadge{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:600;
  padding:4px 10px;border-radius:20px}
.abadge-on{background:rgba(34,197,94,.15);color:var(--green);border:1px solid rgba(34,197,94,.25)}
.abadge-off{background:rgba(100,116,139,.12);color:var(--muted);border:1px solid rgba(100,116,139,.2)}
.abadge-dot{width:6px;height:6px;border-radius:50%;background:currentColor}
.agrid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
@media(max-width:400px){.agrid{grid-template-columns:1fr}}
.acell{background:var(--card2);border:1px solid var(--brd);border-radius:10px;padding:12px 14px}
.aclabel{font-size:10px;text-transform:uppercase;letter-spacing:.7px;color:var(--muted);
  display:flex;align-items:center;gap:5px;margin-bottom:6px}
.acval{font-size:13px;font-weight:600;line-height:1.4}

/* ── SETUP HEADER ── */
.shdr{display:flex;justify-content:space-between;align-items:center;
  margin-bottom:14px;animation:fu .5s .12s ease both;
  position:relative;z-index:20}
.stitle{font-size:20px;font-weight:800;letter-spacing:-.3px}

/* ── CUSTOM DROPDOWN ── */
.csel{position:relative;min-width:148px}
.csel-cur{display:flex;align-items:center;gap:8px;
  background:var(--card);border:1px solid var(--brd);border-radius:10px;
  padding:9px 13px;cursor:pointer;color:var(--txt);
  font-size:13px;font-weight:500;transition:border-color .2s;user-select:none}
.csel-cur:hover,.csel.op .csel-cur{border-color:var(--brd-h)}
.csel-ic{width:16px;height:16px;flex-shrink:0;display:flex;align-items:center;color:var(--blue2)}
.csel-arr{margin-left:auto;color:var(--muted);transition:transform .2s}
.csel.op .csel-arr{transform:rotate(180deg)}
.csel-drop{position:absolute;right:0;top:calc(100% + 6px);min-width:100%;
  background:var(--card);border:1px solid rgba(255,255,255,.1);border-radius:12px;
  overflow:hidden;z-index:200;display:none;
  box-shadow:0 16px 40px rgba(0,0,0,.5)}
.csel.op .csel-drop{display:block}
.csel-opt{display:flex;align-items:center;gap:10px;padding:10px 14px;
  cursor:pointer;font-size:13px;color:var(--txt);transition:background .15s}
.csel-opt:hover{background:rgba(255,255,255,.05)}
.csel-opt.act{background:rgba(59,130,246,.12);color:var(--blue2)}
.csel-oi{width:16px;height:16px;color:var(--blue2);flex-shrink:0;
  display:flex;align-items:center;justify-content:center}

/* ── TABS ── */
.tabs{background:var(--card);border:1px solid var(--brd);border-radius:12px;
  padding:4px;margin-bottom:16px;display:flex;gap:4px;
  animation:fu .5s .18s ease both}
.tab{flex:1;padding:9px 14px;border-radius:8px;border:none;background:transparent;
  color:var(--muted);font-size:14px;font-weight:600;cursor:pointer;transition:all .2s}
.tab.active{background:rgba(59,130,246,.18);color:var(--blue2);border:1px solid rgba(59,130,246,.25)}

/* ── STEP CARDS ── */
.step{background:var(--card);border:1px solid var(--brd);border-radius:14px;
  padding:18px 20px;margin-bottom:10px;
  animation:fu .45s ease both}
.step:nth-child(1){animation-delay:.22s}
.step:nth-child(2){animation-delay:.28s}
.step:nth-child(3){animation-delay:.34s}
.step:nth-child(4){animation-delay:.40s}
.shead{display:flex;align-items:center;gap:12px;margin-bottom:10px}
.sic{width:36px;height:36px;border-radius:10px;
  display:flex;align-items:center;justify-content:center;flex-shrink:0}
.ic-b{background:rgba(59,130,246,.2);border:1px solid rgba(59,130,246,.32);color:var(--blue2)}
.ic-g{background:rgba(34,197,94,.18);border:1px solid rgba(34,197,94,.3);color:var(--green)}
.stit{font-size:15px;font-weight:700}
.sdesc{font-size:13px;color:var(--muted);line-height:1.56;margin-bottom:14px}
.sdesc.last{margin-bottom:0}
.btns{display:flex;flex-wrap:wrap;gap:8px}

/* ── BUTTONS ── */
.sbtn{display:inline-flex;align-items:center;gap:7px;
  padding:10px 18px;border-radius:10px;
  font-size:13px;font-weight:600;
  cursor:pointer;border:none;text-decoration:none;
  transition:all .2s}
.sbtn:hover{opacity:.85;transform:translateY(-1px)}
.sbtn-p{background:#2563eb;color:#fff;border:1px solid transparent}
.sbtn-p:hover{background:#3b82f6;opacity:1}
.sbtn-o{background:var(--bg-btn);color:var(--blue2);border:1px solid rgba(59,130,246,.3)}
.sbtn-o:hover{background:rgba(59,130,246,.18);border-color:rgba(59,130,246,.5);opacity:1}

/* ── TOAST ── */
.toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);
  background:#2563eb;color:#fff;padding:11px 24px;border-radius:12px;
  font-weight:700;font-size:14px;opacity:0;
  transition:opacity .3s;pointer-events:none;z-index:1000}
.toast.show{opacity:1}
</style>
</head>
<body>
<div class="wrap">

  <div class="hdr">
    <div class="logo"><span class="logo-ds">DS</span><span class="logo-vpn">-VPN</span></div>
    <div class="hdr-btns">
      <button class="hdr-btn" onclick="copyUrl()" title="Скопировать ссылку">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
      </button>
      <a href="https://t.me/ds_vpnsupport" class="hdr-btn" title="Поддержка" target="_blank">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 5L2 12.5l7 1M21 5l-2.5 15L9 13.5M21 5L9 13.5m0 0v5.5l3.5-3.5"/></svg>
      </a>
    </div>
  </div>

  <div class="ucard">
    <div class="utop">
      <div class="uav"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M5 12l5 5L20 7"/></svg></div>
      <div class="uname">{{USERNAME}}</div>
    </div>
    <div class="usub">{{EXPIRES_IN}}</div>
    <div class="ugrid">
      <div class="ucell">
        <div class="ulabel"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>Имя пользователя</div>
        <div class="uval">{{USERNAME}}</div>
      </div>
      <div class="ucell">
        <div class="ulabel ig"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12l5 5L20 7"/></svg>Статус</div>
        <div class="uval {{STATUS_CLASS}}">{{STATUS_TEXT}}</div>
      </div>
      <div class="ucell">
        <div class="ulabel io"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>Истекает</div>
        <div class="uval">{{EXPIRY}}</div>
      </div>
      <div class="ucell">
        <div class="ulabel io"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 16V4m0 0L3 8m4-4 4 4M17 8v12m0 0 4-4m-4 4-4-4"/></svg>Трафик</div>
        <div class="uval">{{TRAFFIC}}</div>
      </div>
    </div>
  </div>

  <div id="actcard"></div>

  <div class="shdr">
    <div class="stitle">Установка</div>
    <div class="csel" id="csel">
      <div class="csel-cur" id="ccur" onclick="togSel(event)">
        <span class="csel-ic" id="cic"></span>
        <span id="ctxt">iOS</span>
        <svg class="csel-arr" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M6 9l6 6 6-6"/></svg>
      </div>
      <div class="csel-drop" id="cdrop"></div>
    </div>
  </div>

  <div class="tabs"><button class="tab active">Happ</button></div>
  <div id="steps"></div>

</div>
<div class="toast" id="toast">✓ Ссылка скопирована</div>
<script>
var U='{{SAFE_URL_JS}}';
var ACT={{ACTIVITY_JSON}};

function timeAgo(iso){
  if(!iso)return'—';
  var d=new Date(iso),now=new Date(),diff=Math.floor((now-d)/1000);
  if(diff<60)return'Только что';
  if(diff<3600)return Math.floor(diff/60)+' мин. назад';
  if(diff<86400)return Math.floor(diff/3600)+' ч. назад';
  return Math.floor(diff/86400)+' д. назад';
}
function fmtDate(iso){
  if(!iso)return'—';
  var d=new Date(iso);
  var mo=['янв','фев','мар','апр','май','июн','июл','авг','сен','окт','ноя','дек'];
  return d.getDate()+' '+mo[d.getMonth()]+' '+d.getFullYear();
}
function renderAct(){
  var el=document.getElementById('actcard');
  if(!ACT||(!ACT.onlineAt&&!ACT.firstConnectedAt)){el.style.display='none';return;}
  var onlineAt=ACT.onlineAt||null;
  var firstAt=ACT.firstConnectedAt||null;
  var isOnline=onlineAt&&(new Date()-new Date(onlineAt)<5*60*1000);
  var badge=isOnline
    ?'<span class="abadge abadge-on"><span class="abadge-dot"></span>Онлайн</span>'
    :'<span class="abadge abadge-off"><span class="abadge-dot"></span>Оффлайн</span>';
  el.innerHTML='<div class="acard">'
    +'<div class="acard-hdr"><div class="acard-title">Активность</div>'+badge+'</div>'
    +'<div class="agrid">'
    +'<div class="acell"><div class="aclabel"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>Последний сеанс</div><div class="acval">'+timeAgo(onlineAt)+'</div></div>'
    +'<div class="acell"><div class="aclabel"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 2v4M16 2v4M3 10h18M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z"/></svg>Дата подписки</div><div class="acval">'+fmtDate(firstAt)+'</div></div>'
    +'</div>'
    +'</div>';
}
renderAct();
var PI={
  ios:'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M8.286 7.008c-3.216 0-4.286 3.23-4.286 5.92c0 3.229 2.143 8.072 4.286 8.072c1.165-.05 1.799-.538 3.214-.538c1.406 0 1.607.538 3.214.538s4.286-3.229 4.286-5.381c-.03-.011-2.649-.434-2.679-3.23c-.02-2.335 2.589-3.179 2.679-3.228c-1.096-1.606-3.162-2.113-3.75-2.153c-1.535-.12-3.032 1.077-3.75 1.077c-.729 0-2.036-1.077-3.214-1.077z"/><path d="M12 4a2 2 0 0 0 2-2a2 2 0 0 0-2 2"/></svg>',
  android:'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 10v6"/><path d="M20 10v6"/><path d="M7 9h10v8a1 1 0 0 1-1 1h-8a1 1 0 0 1-1-1v-8a5 5 0 0 1 10 0"/><path d="M8 3l1 2"/><path d="M16 3l-1 2"/><path d="M9 18v3"/><path d="M15 18v3"/></svg>',
  macos:'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 5a1 1 0 0 1 1-1h16a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-16a1 1 0 0 1-1-1z"/><path d="M7 8v1"/><path d="M17 8v1"/><path d="M12.5 4c-.654 1.486-1.26 3.443-1.5 9h2.5c-.19 2.867.094 5.024.5 7"/><path d="M7 15.5c3.667 2 6.333 2 10 0"/></svg>',
  windows:'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M17.8 20l-12-1.5c-1-.1-1.8-.9-1.8-1.9v-9.2c0-1 .8-1.8 1.8-1.9l12-1.5c1.2-.1 2.2.8 2.2 1.9v12.1c0 1.2-1.1 2.1-2.2 1.9z"/><path d="M12 5v14"/><path d="M4 12h16"/></svg>',
  androidTV:'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 9a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-14a2 2 0 0 1-2-2z"/><path d="M16 3l-4 4-4-4"/></svg>',
  appleTV:'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 9a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-14a2 2 0 0 1-2-2z"/><path d="M16 3l-4 4-4-4"/></svg>'
};
var PN={ios:'iOS',android:'Android',macos:'macOS',windows:'Windows',androidTV:'Android TV',appleTV:'Apple TV'};
var PK=['ios','android','macos','windows','androidTV','appleTV'];
var ICO={
  dl:'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/><path d="M7 11l5 5 5-5"/><path d="M12 4v12"/></svg>',
  cl:'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M19 18a3.5 3.5 0 0 0 0-7h-1a5 4.5 0 0 0-11-2 4.6 4.4 0 0 0-2.1 8.4"/><path d="M12 13v9"/><path d="M9 19l3 3 3-3"/></svg>',
  ok:'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M5 12l5 5L20 7"/></svg>',
  ex:'<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>',
  pl:'<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>'
};
var P={
  ios:{steps:[
    {i:'dl',c:'ic-b',t:'Установка приложения',d:'Откройте страницу в App Store и установите приложение. В окне разрешения VPN-конфигурации нажмите Allow и введите пароль.',b:[
      {tx:'App Store (RU)',u:'https://apps.apple.com/ru/app/happ-proxy-utility-plus/id6746188973',ic:'ex',cl:'sbtn-o',nb:1},
      {tx:'App Store (Global)',u:'https://apps.apple.com/us/app/happ-proxy-utility/id6504287215',ic:'ex',cl:'sbtn-o',nb:1}
    ]},
    {i:'cl',c:'ic-b',t:'Добавление подписки',d:'Нажмите кнопку ниже — приложение откроется, и подписка добавится автоматически.',b:[
      {tx:'Добавить подписку',u:'happ://add/'+U,ic:'pl',cl:'sbtn-p',nb:0}
    ]},
    {i:'ok',c:'ic-g',t:'Подключение и использование',d:'В главном разделе нажмите большую кнопку включения для подключения к VPN. Не забудьте выбрать сервер в списке серверов.',b:[]}
  ]},
  android:{steps:[
    {i:'dl',c:'ic-b',t:'Установка приложения',d:'Откройте Google Play и установите приложение. Или скачайте APK напрямую, если Google Play недоступен.',b:[
      {tx:'Google Play',u:'https://play.google.com/store/apps/details?id=com.happproxy',ic:'ex',cl:'sbtn-o',nb:1},
      {tx:'Скачать APK',u:'https://github.com/Happ-proxy/happ-android/releases/latest/download/Happ.apk',ic:'dl',cl:'sbtn-o',nb:1}
    ]},
    {i:'cl',c:'ic-b',t:'Добавление подписки',d:'Нажмите кнопку ниже, чтобы добавить подписку.',b:[
      {tx:'Добавить подписку',u:'happ://add/'+U,ic:'pl',cl:'sbtn-p',nb:0}
    ]},
    {i:'ok',c:'ic-g',t:'Подключение и использование',d:'Откройте приложение и подключитесь к серверу.',b:[]}
  ]},
  macos:{steps:[
    {i:'dl',c:'ic-b',t:'Установка приложения',d:'Выберите версию для вашего устройства и нажмите кнопку ниже.',b:[
      {tx:'App Store (RU)',u:'https://apps.apple.com/ru/app/happ-proxy-utility-plus/id6746188973',ic:'ex',cl:'sbtn-o',nb:1},
      {tx:'App Store (Global)',u:'https://apps.apple.com/us/app/happ-proxy-utility/id6504287215',ic:'ex',cl:'sbtn-o',nb:1}
    ]},
    {i:'cl',c:'ic-b',t:'Добавление подписки',d:'Нажмите кнопку ниже — приложение откроется, и подписка добавится автоматически.',b:[
      {tx:'Добавить подписку',u:'happ://add/'+U,ic:'pl',cl:'sbtn-p',nb:0}
    ]},
    {i:'ok',c:'ic-g',t:'Подключение и использование',d:'В главном разделе нажмите большую кнопку включения для подключения к VPN.',b:[]}
  ]},
  windows:{steps:[
    {i:'dl',c:'ic-b',t:'Установка приложения',d:'Нажмите на кнопку ниже и установите приложение.',b:[
      {tx:'Windows',u:'https://github.com/Happ-proxy/happ-desktop/releases/latest/download/setup-Happ.x64.exe',ic:'dl',cl:'sbtn-o',nb:1}
    ]},
    {i:'cl',c:'ic-b',t:'Добавление подписки',d:'Нажмите кнопку ниже — приложение откроется, и подписка добавится автоматически.',b:[
      {tx:'Добавить подписку',u:'happ://add/'+U,ic:'pl',cl:'sbtn-p',nb:0}
    ]},
    {i:'ok',c:'ic-g',t:'Подключение и использование',d:'В главном разделе нажмите большую кнопку включения для подключения к VPN. При необходимости выберите другой сервер из списка.',b:[]}
  ]},
  androidTV:{steps:[
    {i:'dl',c:'ic-b',t:'Установка приложения',d:'Откройте Google Play и установите приложение, или скачайте APK напрямую.',b:[
      {tx:'Google Play',u:'https://play.google.com/store/apps/details?id=com.happproxy',ic:'ex',cl:'sbtn-o',nb:1},
      {tx:'Скачать APK',u:'https://github.com/Happ-proxy/happ-android/releases/latest/download/Happ.apk',ic:'dl',cl:'sbtn-o',nb:1}
    ]},
    {i:'dl',c:'ic-b',t:'Инструкции по установке',d:'Подробные инструкции по настройке на вашем устройстве.',b:[
      {tx:'На русском',u:'https://www.happ.su/main/ru/faq/android-tv',ic:'ex',cl:'sbtn-o',nb:1}
    ]},
    {i:'cl',c:'ic-b',t:'Добавление подписки',d:'Нажмите кнопку ниже (если страница открыта на телевизоре).',b:[
      {tx:'Добавить подписку',u:'happ://add/'+U,ic:'pl',cl:'sbtn-p',nb:0}
    ]},
    {i:'ok',c:'ic-g',t:'Подключение и использование',d:'Откройте приложение и подключитесь к серверу.',b:[]}
  ]},
  appleTV:{steps:[
    {i:'dl',c:'ic-b',t:'Установка приложения',d:'Откройте App Store на Apple TV, установите приложение и разрешите VPN-конфигурацию.',b:[
      {tx:'App Store',u:'https://apps.apple.com/us/app/happ-proxy-utility-for-tv/id6748297274',ic:'ex',cl:'sbtn-o',nb:1}
    ]},
    {i:'dl',c:'ic-b',t:'Инструкции по установке',d:'Подробные инструкции по настройке на вашем устройстве.',b:[
      {tx:'На русском',u:'https://www.happ.su/main/ru/faq/android-tv',ic:'ex',cl:'sbtn-o',nb:1}
    ]},
    {i:'cl',c:'ic-b',t:'Добавление подписки',d:'Нажмите кнопку ниже (если страница открыта на TV).',b:[
      {tx:'Добавить подписку',u:'happ://add/'+U,ic:'pl',cl:'sbtn-p',nb:0}
    ]},
    {i:'ok',c:'ic-g',t:'Подключение и использование',d:'Откройте приложение и подключитесь к серверу.',b:[]}
  ]}
};

function renderSteps(k){
  var cfg=P[k];if(!cfg)return;
  var h='';
  for(var i=0;i<cfg.steps.length;i++){
    var s=cfg.steps[i];
    var bh='';
    if(s.b.length){
      bh='<div class="btns">';
      for(var j=0;j<s.b.length;j++){
        var b=s.b[j];
        bh+='<a href="'+b.u+'" class="sbtn '+b.cl+'"'+(b.nb?' target="_blank"':'')+'>'+ICO[b.ic]+' '+b.tx+'</a>';
      }
      bh+='</div>';
    }
    var last=s.b.length===0;
    h+='<div class="step"><div class="shead"><div class="sic '+s.c+'">'+ICO[s.i]+'</div><div class="stit">'+s.t+'</div></div><div class="sdesc'+(last?' last':'')+'">'+s.d+'</div>'+bh+'</div>';
  }
  document.getElementById('steps').innerHTML=h;
}

function buildDrop(){
  var h='';
  for(var i=0;i<PK.length;i++){
    var k=PK[i];
    h+='<div class="csel-opt" data-v="'+k+'" onclick="pick(this.dataset.v)"><span class="csel-oi">'+PI[k]+'</span>'+PN[k]+'</div>';
  }
  document.getElementById('cdrop').innerHTML=h;
}

function setUI(k){
  document.getElementById('cic').innerHTML=PI[k];
  document.getElementById('ctxt').textContent=PN[k];
  var opts=document.querySelectorAll('.csel-opt');
  for(var i=0;i<opts.length;i++) opts[i].classList.toggle('act',opts[i].dataset.v===k);
}

function pick(k){
  document.getElementById('csel').classList.remove('op');
  setUI(k);renderSteps(k);
}

function togSel(e){
  e.stopPropagation();
  document.getElementById('csel').classList.toggle('op');
}

document.addEventListener('click',function(){
  document.getElementById('csel').classList.remove('op');
});

function detectOS(){
  var ua=navigator.userAgent.toLowerCase();
  if(/ipad|iphone|ipod/.test(ua))return'ios';
  if(/macintosh|mac os x/.test(ua))return'macos';
  if(/android/.test(ua))return'android';
  if(/windows/.test(ua))return'windows';
  return'ios';
}

function copyUrl(){
  if(navigator.clipboard){navigator.clipboard.writeText(U).then(showT).catch(fb);}else{fb();}
  function fb(){var e=document.createElement('textarea');e.value=U;document.body.appendChild(e);e.select();document.execCommand('copy');document.body.removeChild(e);showT();}
}
function showT(){var t=document.getElementById('toast');t.classList.add('show');setTimeout(function(){t.classList.remove('show');},2000);}

buildDrop();
var ip=detectOS();
setUI(ip);renderSteps(ip);
</script>
</body>
</html>"""


def _days_word(n: int) -> str:
    n_abs = abs(n)
    if 11 <= n_abs % 100 <= 19:
        return "дней"
    r = n_abs % 10
    if r == 1:
        return "день"
    if 2 <= r <= 4:
        return "дня"
    return "дней"


def _proxy_headers(request: Request) -> dict:
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length", "accept-encoding")
    }
    headers["X-Forwarded-Proto"] = "https"
    headers["X-Forwarded-For"] = request.client.host if request.client else "127.0.0.1"
    return headers


def _render_page(data: dict, sub_url: str, activity: dict | None = None) -> str:
    if not data.get("isFound"):
        return (
            "<!doctype html><html><head><meta charset=UTF-8><title>DS-VPN</title></head>"
            "<body style='background:#07080f;color:#e2e8f0;font-family:sans-serif;"
            "display:flex;align-items:center;justify-content:center;height:100vh;margin:0'>"
            "<h2>Подписка не найдена</h2></body></html>"
        )

    user = data.get("user", {})
    days_left = user.get("daysLeft", 0)
    traffic_used = user.get("trafficUsed", "—")
    traffic_limit = user.get("trafficLimit", "")
    is_active = user.get("isActive", False)
    expires_at = user.get("expiresAt", "")
    username = user.get("username") or user.get("shortUuid", "—")

    try:
        dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        expiry_str = f"{dt.day} {_RU_MONTHS[dt.month - 1]} {dt.year}"
    except Exception:
        expiry_str = "—"

    if days_left > 0:
        expires_in = f"Истекает через {days_left} {_days_word(days_left)}"
    elif days_left == 0:
        expires_in = "Истекает сегодня"
    else:
        expires_in = "Подписка истекла"

    traffic_str = (
        f"{traffic_used} / {traffic_limit}"
        if traffic_limit and traffic_limit not in ("0", "0 B")
        else traffic_used
    )
    status_text = "Активна" if is_active else "Неактивна"
    status_class = "s-act" if is_active else "s-ina"

    safe_js = sub_url.replace("\\", "\\\\").replace("'", "\\'")
    activity_json = _json.dumps(activity or {})

    return (
        _PAGE_TEMPLATE
        .replace("{{USERNAME}}", _html.escape(username))
        .replace("{{EXPIRES_IN}}", _html.escape(expires_in))
        .replace("{{EXPIRY}}", _html.escape(expiry_str))
        .replace("{{TRAFFIC}}", _html.escape(traffic_str))
        .replace("{{STATUS_CLASS}}", status_class)
        .replace("{{STATUS_TEXT}}", status_text)
        .replace("{{SAFE_URL_JS}}", safe_js)
        .replace("{{ACTIVITY_JSON}}", activity_json)
    )


@router.get("/sub/{token}")
async def subscription_proxy(token: str, request: Request):
    accept = request.headers.get("accept", "")

    if "text/html" in accept:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{_REMNAWAVE}/api/sub/{token}",
                headers=_proxy_headers(request),
            )
        if resp.status_code == 200:
            try:
                data = resp.json()
                sub_url = data.get("subscriptionUrl") or f"https://dsvpnservice.ru:8443/sub/{token}"
                username = data.get("user", {}).get("username", "")
                activity: dict = {}
                if username:
                    try:
                        from bot.services.remnawave import remnawave
                        a = await remnawave._request("GET", f"/users/by-username/{username}")
                        activity = a.json().get("response", {}).get("userTraffic", {})
                    except Exception:
                        pass
                return HTMLResponse(content=_render_page(data, sub_url, activity))
            except Exception:
                pass
        return HTMLResponse(
            content=(
                "<html><body style='background:#07080f;color:#e2e8f0;font-family:sans-serif;"
                "display:flex;align-items:center;justify-content:center;height:100vh'>"
                "<h2>Подписка не найдена</h2></body></html>"
            ),
            status_code=404,
        )

    # VPN client: forward raw config
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{_REMNAWAVE}/api/sub/{token}",
            headers=_proxy_headers(request),
            params=dict(request.query_params),
        )

    extra_headers = {}
    for h in ("content-disposition", "profile-title", "profile-update-interval",
              "subscription-userinfo", "profile-web-page-url", "support-url", "announce"):
        if h in resp.headers:
            extra_headers[h] = resp.headers[h]

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type", "text/plain"),
        headers=extra_headers,
    )


@router.get("/xray/{token}")
async def xray_config(token: str, request: Request):
    """Return full multi-server Xray JSON config for auto-selection clients."""
    from bot.database.models import VpnServer
    from bot.services.xray_config import build_xray_config

    # Validate token via Remnawave and get user UUID
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{_REMNAWAVE}/api/sub/{token}",
            headers=_proxy_headers(request),
        )

    if resp.status_code != 200:
        return JSONResponse({"error": "subscription not found"}, status_code=404)

    try:
        data = resp.json()
        if not data.get("isFound"):
            return JSONResponse({"error": "subscription not found"}, status_code=404)
        user_uuid = data.get("user", {}).get("uuid") or data.get("user", {}).get("shortUuid")
        if not user_uuid:
            return JSONResponse({"error": "user uuid not found"}, status_code=404)
    except Exception:
        return JSONResponse({"error": "invalid response"}, status_code=500)

    # Load active servers from DB
    from bot.database.session import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(VpnServer).where(VpnServer.is_active == True).order_by(VpnServer.is_backup, VpnServer.id)
        )
        servers = result.scalars().all()

    if not servers:
        return JSONResponse({"error": "no servers configured"}, status_code=503)

    config = build_xray_config(user_uuid=user_uuid, servers=servers)

    username = data.get("user", {}).get("username", "user")
    days_left = data.get("user", {}).get("daysLeft", 0)

    return Response(
        content=_json.dumps(config, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={
            "content-disposition": f'attachment; filename="ds-vpn-{username}.json"',
            "profile-title": f"DS-VPN | {username}",
            "profile-update-interval": "24",
            "subscription-userinfo": f"expire={days_left}",
        },
    )


_STATIC_PREFIXES = ("assets/", "splash_screens/", "favicon", "manifest", "apple-touch", "pwa-")


@router.get("/{path:path}")
async def remnawave_proxy(path: str, request: Request):
    if not (any(path.startswith(p) for p in _STATIC_PREFIXES) or path.startswith("api/")):
        return Response(status_code=404)

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{_REMNAWAVE}/{path}",
            headers=_proxy_headers(request),
            params=dict(request.query_params),
        )
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type"),
    )
