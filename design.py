"""サイト共通の紙面デザイン(新聞の金利欄風)。新しい題材のサイトもこれを使う。"""

FONTS_LINK = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
              '<link href="https://fonts.googleapis.com/css2?family=Zilla+Slab:wght@700&family=Shippori+Mincho+B1:wght@800&family=Shippori+Mincho:wght@400;700&family=Libre+Franklin:wght@500&display=swap" rel="stylesheet">')

CSS = """/* design: newsprint (Hallmark theme, by request, hand-adapted for Japanese) · genre: editorial · signature: 今朝の最高金利を紙面の見出し数字として置く */
/* critique: 相場表として読むページ。装飾は罫線だけ、色はれんが色を5%未満、数字は表の右端に揃える */
:root{
  --color-paper:oklch(94% 0.011 92);--color-paper-2:oklch(90.5% 0.015 88);
  --color-ink:oklch(17% 0.012 60);--color-ink-2:oklch(27% 0.012 58);--color-muted:oklch(46% 0.014 60);
  --color-rule:oklch(68% 0.016 75);--color-rule-2:oklch(34% 0.012 60);
  --color-accent:oklch(44% 0.13 32);--color-focus:oklch(48% 0.17 32);
  --font-display:"Zilla Slab","Shippori Mincho B1",ui-serif,serif;
  --font-body:"Shippori Mincho","Hiragino Mincho ProN","Yu Mincho",ui-serif,serif;
  --font-agate:"Libre Franklin",ui-sans-serif,sans-serif;
  --rule-hair:1px;--measure:68rem;
  --space-xs:.25rem;--space-sm:.5rem;--space-md:1rem;--space-lg:1.5rem;--space-xl:2.5rem;--space-2xl:4rem;
  --text-sm:.875rem;--text-base:1.0625rem;--text-title:1.375rem;--text-display:clamp(2.25rem,5.5vw,4rem);--text-figure:clamp(2.75rem,7vw,5.25rem);
}
html,body{overflow-x:clip}
body{margin:0;background:var(--color-paper);color:var(--color-ink);font:400 var(--text-base)/1.65 var(--font-body);-webkit-text-size-adjust:100%}
.wrap{max-width:var(--measure);margin-inline:auto;padding-inline:clamp(16px,4vw,40px)}
a{color:var(--color-accent);text-decoration-color:var(--color-accent);text-underline-offset:.18em}
a:hover{text-decoration-thickness:2px}
a:focus-visible,input:focus-visible,label:focus-within{outline:2px solid var(--color-focus);outline-offset:3px}
.rule2{box-sizing:content-box;height:2px;border:0;border-block:var(--rule-hair) solid var(--color-rule-2);margin:0}
.rule{height:0;border:0;border-top:var(--rule-hair) solid var(--color-rule);margin:0}
h1,h2,h3{font-family:var(--font-display);font-weight:800;color:var(--color-ink);margin:0;overflow-wrap:break-word;min-width:0}
.meta{font-size:var(--text-sm);color:var(--color-muted)}

.mast{display:flex;justify-content:space-between;align-items:baseline;gap:var(--space-md);flex-wrap:wrap;padding-block:var(--space-lg) var(--space-sm)}
.mast .name{font:800 var(--text-title)/1.2 var(--font-display);text-decoration:none;color:var(--color-ink)}

.lead{display:grid;grid-template-columns:minmax(0,7fr) minmax(0,5fr);gap:var(--space-xl);padding-block:var(--space-xl)}
.lead h1{font-size:var(--text-display);line-height:1.15;letter-spacing:-.01em}
.lead p{margin:var(--space-md) 0 var(--space-lg);max-width:34em}
.act{display:inline-block;background:var(--color-ink);color:var(--color-paper);font:700 .9375rem/1 var(--font-display);padding:var(--space-md) var(--space-lg);text-decoration:none}
.act:hover{background:var(--color-ink-2);text-decoration:none}
.score{border-left:var(--rule-hair) solid var(--color-rule);padding-left:var(--space-xl);display:grid;align-content:start;gap:var(--space-lg)}
.score>div{border-bottom:var(--rule-hair) solid var(--color-rule);padding-bottom:var(--space-md)}
.score .fig{font:500 var(--text-figure)/1 var(--font-agate);font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.score .fig small{font-size:.4em;margin-left:.1em}
.score .what{font-size:var(--text-sm)}

.tools{display:flex;flex-wrap:wrap;gap:var(--space-sm) var(--space-lg);align-items:baseline;padding-block:var(--space-md)}
.tools nav{display:flex;flex-wrap:wrap;gap:var(--space-xs) var(--space-md)}
.tools label{cursor:pointer;font-size:var(--text-sm)}
.tools input{accent-color:var(--color-ink);margin-right:var(--space-xs)}

section{padding-block:var(--space-xl) 0;scroll-margin-top:var(--space-md)}
section h2{font-size:var(--text-title);padding-bottom:var(--space-sm)}
.list{list-style:none;margin:0;padding:0;border-top:var(--rule-hair) solid var(--color-rule-2)}
.row{display:grid;grid-template-columns:minmax(0,15rem) minmax(0,1fr) 7rem 6.5rem;gap:var(--space-md);align-items:baseline;padding-block:var(--space-md);border-bottom:var(--rule-hair) solid var(--color-rule)}
.row .bank{font-weight:700;line-height:1.4}
.row .bank a{color:var(--color-ink);text-decoration:none}
.row .bank a:hover{text-decoration:underline}
.row .prod{font-size:var(--text-sm);line-height:1.6;color:var(--color-ink-2)}
.row .prod .cond{color:var(--color-muted)}
.row .end{font-size:var(--text-sm);color:var(--color-muted);text-align:right}
.row .rate{font:500 1.5rem/1 var(--font-agate);font-variant-numeric:tabular-nums;text-align:right}
.row .rate small{font-size:.55em}
.note{color:var(--color-accent)}
.pr{font-size:.75em;color:var(--color-muted);border:var(--rule-hair) solid var(--color-rule);padding:0 .3em;margin-left:.4em}
.hide-new .row[data-new="1"]{display:none}

.colophon{margin-top:var(--space-2xl);padding-block:var(--space-lg) var(--space-2xl);display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:var(--space-xl);font-size:var(--text-sm);color:var(--color-ink-2)}
.colophon h3{font-size:1rem;margin-bottom:var(--space-sm)}
.colophon p{margin:0 0 var(--space-sm)}

@media (max-width:760px){
  .lead{grid-template-columns:minmax(0,1fr);gap:var(--space-lg);padding-block:var(--space-lg)}
  .score{border-left:0;padding-left:0;grid-template-columns:repeat(3,minmax(0,1fr));gap:var(--space-md)}
  .score .fig{font-size:2rem}
  .row{grid-template-columns:minmax(0,1fr) auto;gap:var(--space-xs) var(--space-md)}
  .row .bank{grid-column:1}.row .rate{grid-column:2;grid-row:1}
  .row .prod{grid-column:1/-1}.row .end{grid-column:1/-1;text-align:left}
  .colophon{grid-template-columns:minmax(0,1fr)}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
"""
