"""导出为单文件 HTML（多卷）。团队成员零安装使用。

数据全部内嵌，双击即用；检索逻辑与 engine.py 一致（词覆盖 + 连续词串 + 跨句合并）。
"""
import json, os, glob, re

ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    vmeta = {}
    vm = os.path.join(ROOT, "corpus/volumes.json")
    if os.path.exists(vm):
        vmeta = json.load(open(vm, encoding="utf-8"))

    chapters, ch_id, rows = [], {}, []
    counts = {}
    for fp in sorted(glob.glob(os.path.join(ROOT, "corpus/vol*_sent.jsonl"))):
        vol = int(re.search(r"vol(\d+)_sent", os.path.basename(fp)).group(1))
        counts[vol] = 0
        for line in open(fp, encoding="utf-8"):
            r = json.loads(line)
            key = (vol, r["chapter"])
            if key not in ch_id:
                ch_id[key] = len(chapters)
                chapters.append([vol, r["chapter"]])
            rows.append([r["en"], r.get("zh") or "", ch_id[key], r.get("page"),
                         r.get("en_i"), r.get("en_s")])
            counts[vol] += 1

    payload = json.dumps({
        "ch": chapters,
        "rows": rows,
        "meta": {k: {"title": v.get("title", f"第{k}卷"), "source": v.get("source", "")}
                 for k, v in vmeta.items()},
    }, ensure_ascii=False, separators=(",", ":"))

    html = TEMPLATE.replace("/*__DATA__*/null", payload)
    out = os.path.join(ROOT, "dist")
    os.makedirs(out, exist_ok=True)
    fp = os.path.join(out, "马恩引文定位.html")
    open(fp, "w", encoding="utf-8").write(html)
    print(f"{fp}  {os.path.getsize(fp)/1024/1024:.2f} MB  句 {len(rows)}  章 {len(chapters)}  卷 {sorted(counts)}")


TEMPLATE = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>马恩引文定位</title>
<style>
:root{--bg:#faf9f6;--panel:#fff;--ink:#1f1e1c;--muted:#6b6862;--line:#e3e0d8;
 --accent:#8a2f2b;--warn:#8a5b1f}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);line-height:1.75;
 font-family:"Songti SC","Source Han Serif SC","Noto Serif CJK SC",Georgia,serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:880px;margin:0 auto;padding:40px 24px 72px}
h1{font-size:22px;font-weight:600;margin:0 0 6px;letter-spacing:.02em}
.sub{color:var(--muted);font-size:13px;margin:0 0 24px;font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
.box{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:18px}
textarea{width:100%;min-height:104px;border:0;outline:0;resize:vertical;
 font-family:"Iowan Old Style",Georgia,serif;font-size:15px;line-height:1.7;background:transparent;color:var(--ink)}
textarea::placeholder{color:#b6b2a8}
.bar{display:flex;gap:10px;align-items:center;margin-top:12px;padding-top:14px;
 border-top:1px solid var(--line);font-family:system-ui,-apple-system,"Segoe UI",sans-serif;flex-wrap:wrap}
button{font:inherit;font-size:13px;padding:7px 16px;border-radius:6px;cursor:pointer;
 border:1px solid var(--accent);background:var(--accent);color:#fff}
button.ghost{background:transparent;color:var(--accent)}
select{font:inherit;font-size:12.5px;padding:6px 8px;border-radius:6px;
 border:1px solid var(--line);background:var(--panel);color:var(--ink)}
.hint{margin-left:auto;font-size:12px;color:var(--muted)}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:18px 20px;margin-top:14px}
.card.best{border-left:3px solid var(--accent)}
.ref{display:flex;flex-wrap:wrap;gap:8px;align-items:baseline;margin-bottom:10px;
 font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
.vol{font-size:12px;color:#fff;background:var(--accent);border-radius:4px;padding:0 6px}
.chap{font-size:13px;color:var(--accent);font-weight:500}
.page{font-size:13px;color:var(--muted)}
.conf{margin-left:auto;font-size:12px;color:var(--muted)}
.zh{font-size:16px;margin:0 0 10px;text-indent:2em}
.en{font-size:12.5px;color:var(--muted);font-family:"Iowan Old Style",Georgia,serif;
 border-left:2px solid var(--line);padding-left:12px;line-height:1.6}
.copy{margin-top:12px;font-size:12px;padding:4px 10px}
.empty{color:var(--muted);font-size:13px;margin-top:20px;text-align:center}
.warn{color:var(--warn);font-size:12.5px;margin-top:10px;
 font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
footer{margin-top:44px;padding-top:18px;border-top:1px solid var(--line);color:var(--muted);
 font-size:12px;font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
kbd{background:#efede7;border-radius:3px;padding:1px 5px;font-size:11px}
</style>
</head>
<body>
<div class="wrap">
  <h1>马恩引文定位</h1>
  <p class="sub">贴入英文文献中的引文，定位到《马克思恩格斯文集》的中文译文与页码。完全离线，不联网。</p>

  <div class="box">
    <textarea id="q" placeholder="例如：Force is the midwife of every old society pregnant with a new one."></textarea>
    <div class="bar">
      <button id="go">定位</button>
      <button id="clr" class="ghost">清空</button>
      <select id="vol"><option value="">全部卷</option></select>
      <span class="hint"><kbd>Ctrl</kbd> + <kbd>Enter</kbd></span>
    </div>
  </div>
  <div id="out"></div>

  <footer id="foot"></footer>
</div>

<script>
const DATA = /*__DATA__*/null;
const CH = DATA.ch, ROWS = DATA.rows;
const STOP = new Set(("a an the of to in on at by for with from as is are was were be been being "+
"that this these those it its his her their our your my he she they we you i him them us "+
"and or but if then so such not no nor only own same very can will just should now "+
"which who whom whose what when where why how all any both each few more most other some "+
"does do did doing done has have had having would could may might must shall into upon "+
"there here out up down over under again further once also thus therefore however although "+
"because while during before after above below between through against about within without").split(" "));

const words = s => (s||"").toLowerCase().match(/[a-z][a-z'\-]+/g) || [];
const content = w => w.filter(x => !STOP.has(x) && x.length > 2);
const grams = (w,n=3) => { const g=new Set(); for(let i=0;i+n<=w.length;i++) g.add(w.slice(i,i+n).join(" ")); return g; };
const nums = s => new Set(((s||"").match(/\d+(?:[.,]\d+)*/g)||[])
  .map(x=>x.replace(/[,\s]/g,"")).filter(Boolean));
// 引文有数字而中文句对不上，多半是句子配对错位——这是唯一不用模型就能自动做的自检
function numCheck(q, zh){
  const qn=nums(q), zn=nums(zh);
  if(qn.size<2) return "n/a";
  let a=0; for(const x of qn) if(zn.has(x)) a++;
  return a/qn.size>=0.6 ? "ok" : "mismatch";
}

const idx = ROWS.map(r => { const w=words(r[0]); return { c:new Set(content(w)), g:grams(w) }; });
const bySeg = new Map();
ROWS.forEach((r,i)=>{
  const k = CH[r[2]][0] + "|" + r[4];
  if(!bySeg.has(k)) bySeg.set(k,[]);
  bySeg.get(k).push(i);
});

function locate(text, volFilter){
  const w=words(text), qc=new Set(content(w)), qg=grams(w);
  if(!qc.size) return [];
  // 实词不足 4 个时命中率天然虚高（"the rate of profit" 全库几百句都有），按实词数打折
  const nq=qc.size;
  const damp = nq>=4 ? 1 : ({1:0.60, 2:0.75, 3:0.90})[nq] || 0.9;
  const warnQ = nq<4 ? "引文过短，仅作候选参考" : "";
  const hit=[];
  for(let k=0;k<idx.length;k++){
    if(volFilter && CH[ROWS[k][2]][0] !== volFilter) continue;
    const it=idx[k];
    let a=0; for(const x of qc) if(it.c.has(x)) a++;
    let b=0; for(const x of qg) if(it.g.has(x)) b++;
    const cov=qc.size?a/qc.size:0, ng=qg.size?b/qg.size:0;
    const s=(0.45*cov+0.55*ng)*damp;
    if(s>0.12) hit.push([s,cov,ng,k]);
  }
  hit.sort((a,b)=>b[0]-a[0]);
  const out=[], seen=new Set();
  for(const [s,c,n,k] of hit.slice(0,40)){
    const r=ROWS[k];
    let best={s,c,n,k,win:null};
    const grp=bySeg.get(CH[r[2]][0]+"|"+r[4]) || [k];
    const pos=grp.indexOf(k);
    for(const wsize of [2,3]){
      const win=grp.slice(pos,pos+wsize);
      if(win.length<2) continue;
      const txt=win.map(j=>ROWS[j][0]).join(" ");
      const wc=new Set(content(words(txt))), wg=grams(words(txt));
      let a=0; for(const x of qc) if(wc.has(x)) a++;
      let b=0; for(const x of qg) if(wg.has(x)) b++;
      const cov=qc.size?a/qc.size:0, ng=qg.size?b/qg.size:0;
      // 窗口里只要有一句没中文，拼出来的中文就是残缺的，必须算未对齐并降权
      const partial=win.some(j=>!ROWS[j][1]);
      const sc=(0.45*cov+0.55*ng)*(partial?0.72:1)*damp;
      if(sc>best.s+0.02) best={s:sc,c:cov,n:ng,k,win,partial};
    }
    const rr=ROWS[best.k];
    const zh=best.win ? best.win.map(j=>ROWS[j][1]).filter(Boolean).join(" ") : rr[1];
    const partial=best.partial || (best.win?best.win.some(j=>!ROWS[j][1]):!rr[1]);
    const key=rr[2]+"|"+rr[0].slice(0,40);
    if(seen.has(key)) continue;
    seen.add(key);
    const nchk=numCheck(text, zh);
    if(nchk==="mismatch") best.s*=0.75;
    out.push({score:best.s,vol:CH[rr[2]][0],chapter:CH[rr[2]][1],page:rr[3],
              en:best.win?best.win.map(j=>ROWS[j][0]).join(" "):rr[0],
              zh:zh, unaligned:partial, numeric:nchk, warn:warnQ});
    if(out.length>=3) break;
  }
  out.sort((a,b)=>b.score-a.score);
  return out;
}

const esc = s => (s||"").replace(/[&<>]/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));

function render(q){
  const out=document.getElementById("out");
  const vf=document.getElementById("vol").value;
  const res=locate(q, vf?Number(vf):null);
  if(!res.length){ out.innerHTML='<div class="empty">没有找到候选。试试贴入更完整的一句，或换成原文措辞。</div>'; return; }
  out.innerHTML=res.map((r,k)=>{
    const bad=r.unaligned;
    const numBad=r.numeric==="mismatch";
    const pg=r.page?`第 ${r.page} 页`:"页码待核";
    const cls=(k===0&&!bad&&!numBad)?"card best":"card";
    const notes=[];
    if(bad) notes.push("该句未对齐到中文，中文与页码都需人工核");
    if(numBad) notes.push("引文中的数字在中文句里对不上，很可能配错了段");
    if(r.warn) notes.push(r.warn);
    if(k===0 && r.score<0.55) notes.push("匹配度偏低，多为两边段落划分错开所致");
    return `<div class="${cls}">
      <div class="ref"><span class="vol">文集第 ${r.vol} 卷</span>
      <span class="chap">${esc(r.chapter)}</span><span class="page">· ${pg}</span>
      <span class="conf">匹配度 ${(r.score*100).toFixed(0)}%</span></div>
      <p class="zh">${bad?"（该句未对齐到中文，建议人工核对）":esc(r.zh)}</p>
      <div class="en">${esc(r.en)}</div>
      ${notes.map(t=>`<div class="warn">${t}</div>`).join("")}
      ${!bad?`<button class="ghost copy" data-t="《马克思恩格斯文集》第 ${r.vol} 卷，第 ${r.page||"?"} 页">复制出处</button>`:""}
    </div>`;
  }).join("");
  out.querySelectorAll(".copy").forEach(b=>{
    b.onclick = async ()=>{
      const t=b.dataset.t;
      try{ await navigator.clipboard.writeText(t); b.textContent="已复制"; }
      catch(e){ const ta=document.createElement("textarea"); ta.value=t;
        document.body.appendChild(ta); ta.select();
        try{ document.execCommand("copy"); b.textContent="已复制"; }
        catch(_){ b.textContent="请手动复制"; } document.body.removeChild(ta); }
    };
  });
}

(function init(){
  const sel=document.getElementById("vol");
  const vs=[...new Set(CH.map(c=>c[0]))].sort((a,b)=>a-b);
  vs.forEach(v=>{
    const m=DATA.meta[String(v)]||{};
    const o=document.createElement("option");
    o.value=v; o.textContent=`第${v}卷 ${(m.title||"").replace(/^《|》$/g,"")}`;
    sel.appendChild(o);
  });
  const total=ROWS.length, pg=ROWS.filter(r=>r[3]).length;
  document.getElementById("foot").innerHTML=
    `已收录 ${vs.length} 卷、${total.toLocaleString()} 句，其中 ${pg.toLocaleString()} 句带印刷页码。<br>`+
    `语料：MECW（英文）×《马克思恩格斯文集》（人民出版社，2009）。页码取自各卷 PDF 的印刷页码。<br>`+
    `定位为句子级：卷、章、页可靠度较高，<b>中文句子是候选</b>，约四分之一存在配对错位，`+
    `正式引用前请翻到该页核对。带数字的引文会自动核对数字，对不上会明确提示。`;
})();

const q=document.getElementById("q");
document.getElementById("go").onclick=()=>{const v=q.value.trim(); if(v) render(v);};
document.getElementById("clr").onclick=()=>{q.value=""; document.getElementById("out").innerHTML="";};
document.getElementById("vol").onchange=()=>{const v=q.value.trim(); if(v) render(v);};
q.addEventListener("keydown",e=>{if(e.key==="Enter"&&(e.ctrlKey||e.metaKey)){e.preventDefault();document.getElementById("go").click();}});
</script>
</body>
</html>'''


if __name__ == "__main__":
    main()
