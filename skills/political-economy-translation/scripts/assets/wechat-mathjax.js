/* wechat-mathjax.js — 用 MathJax 3 (tex-svg-full) 把公式占位 <span class="woap-math"> 渲染成
 * 自包含行内 <svg>，微信兼容处理（源自墨滴 solveWeChatMath 的核心结论）：
 *   1) SVG 的 width/height 属性移到 style（微信编辑器剥离属性但保留 style）；
 *   2) 在 SVG 内追加一个空 <g> —— 微信会删掉含 transform 的字形 g，
 *      追加空 g 让微信删它、保住字形 g（2024-05-22 微信侧变更后的应急方案）；
 *   3) 行内公式 = <span class="span-inline-equation"><span class="inline-equation" data-formula>svg</span></span>；
 *      块级公式 = <p class="block-equation" data-formula style="text-align:center;overflow-x:auto;margin:…">svg</p>
 *
 * ⚠️ 空行根因（2026-09-04 用户真实微信二分实测定论，取代此前所有 span>section 方案）：
 *   微信编辑器（ProseMirror 内核）会把任何"块级公式容器"当作对象并前后补空段落——
 *   <span><section>、裸 <section>、<div><section> 全部在真实微信里出现前后空行
 *   （用户 A/B 实测：6 组结构仅"<p> 内嵌行内 svg"通过）。唯一干净结构是：
 *   <p style="text-align:center;margin:0.8em 0;"><svg 行内 /></p> —— <p> 是微信原生段落，
 *   行内 svg 不触发对象化，前后零空行。居中由 p 的 text-align:center 完成；
 *   长公式滚动条由 p 的 overflow-x:auto 保留（p 上 inline 样式微信原样保留）。
 *
 * MathJax 用 `svg.fontCache="none"`（每个公式 SVG 自带 path 字形，不依赖共享 defs）。
 * 依赖：static/mathjax/tex-svg-full.js（页面已加载，且 window.MathJax 已配置好）。
 * 对外接口：window.__WECHAT_MATHJAX__.render(latex, display) -> {svg, width, height}
 *           与旧 __WECHAT_SVG__.render 调用签名兼容（供 typeset.html 替换）。
 */
(function (global) {
  'use strict';

  // 微信兼容处理核心：对已渲染好的 mjx-container 做微信兼容处理。
  function wrapForWeChat(svg, latex, display) {
    if (!svg || svg.nodeName.toLowerCase() !== 'svg') return null;

    // 1) width/height 属性 -> style（微信编辑器对属性敏感，保留 style）
    var width = svg.getAttribute('width');
    var height = svg.getAttribute('height');
    if (width) { svg.removeAttribute('width'); }
    if (height) { svg.removeAttribute('height'); }
    svg.style.width = width || '';
    svg.style.height = height || '';
    // 2) MathJax 对带 \tag / mtable 的长公式会在 style 里给 width:100%（配合 min-width），
    //    这会拉伸公式占满整行；改为用 min-width（自然宽度）作为实际宽度，保持紧凑。
    if (display && svg.style.width === '100%') {
      var mw = svg.style.minWidth || '';
      svg.style.width = mw;
    }

    // 3) 追加空 <g>：让微信删它而不是删字形 g
    var gElement = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    svg.appendChild(gElement);

    // 4) 公式容器 + data-formula（存原始 LaTeX）
    //    行内公式 = span.span-inline-equation > span.inline-equation > svg（行内套行内，合法）。
    //    块级公式 = p.block-equation > svg（用户真实微信二分实测：仅此结构零空行；
    //    span>section / 裸 section / div>section 均被微信补空段落）。
    //    居中靠 p 的 text-align:center（行内 svg 同样生效）；长公式滚动条靠 overflow-x:auto。
    //    svg 必须保持"行内"（不设 display:block、不设 margin:0 auto）。
    if (display) {
      var pElement = document.createElement('p');
      pElement.className = 'block-equation';
      pElement.setAttribute('data-formula', latex);
      pElement.style.fontSize = (window.__WX_FONT_SIZE__ || 15) + 'px';
      pElement.style.lineHeight = '2';
      pElement.style.color = window.__WX_TEXT_COLOR__ || '#333';
      pElement.style.textAlign = 'center';
      pElement.style.overflowX = 'auto';
      pElement.style.margin = '0.8em 0';
      pElement.appendChild(svg);
      return pElement;
    }
    var inlineWrapper = document.createElement('span');
    inlineWrapper.className = 'span-inline-equation';
    inlineWrapper.style.cursor = 'pointer';
    var spanElement = document.createElement('span');
    spanElement.className = 'inline-equation';
    spanElement.setAttribute('data-formula', latex);
    spanElement.appendChild(svg);
    inlineWrapper.appendChild(spanElement);
    return inlineWrapper;
  }

  function render(latex, display) {
    if (typeof window === 'undefined') return null;
    if (!window.MathJax || !window.MathJax.tex2svg) {
      return { error: 'MathJax 未加载' };
    }
    var container;
    try {
      // tex2svg 返回 <mjx-container>；em/ex 按正文正文字号语义传入（默认 15px，ex≈em/2）。
      // 公众号排版设置（正文字号）通过 window.__WX_FONT_SIZE__ 传入，公式随正文缩放。
      var wxF = (typeof window !== 'undefined' && window.__WX_FONT_SIZE__)
        ? Number(window.__WX_FONT_SIZE__) : 15;
      if (!(wxF > 0)) wxF = 15;
      container = window.MathJax.tex2svg(String(latex == null ? '' : latex), {
        display: !!display,
        em: wxF,
        ex: wxF / 2,
        containerWidth: 600,
      });
    } catch (e) {
      return { error: 'mathjax_error:' + ((e && e.message) || e), plain: String(latex) };
    }
    if (!container) return { error: 'mathjax_no_output', plain: String(latex) };

    var svg = container.querySelector('svg');
    if (!svg) return { error: 'mathjax_no_svg', plain: String(latex) };

    var holder;
    try {
      holder = wrapForWeChat(svg.cloneNode(true), String(latex), !!display);
    } catch (e) {
      return { error: 'wrap_error:' + ((e && e.message) || e), plain: String(latex) };
    }
    if (!holder) return { error: 'mw_wrap_failed', plain: String(latex) };

    // 尺寸摘要（重新读回 holder 内的 svg style）
    var outSvg = holder.querySelector('svg');
    var w = outSvg ? parseFloat(outSvg.style.width) : 0;
    var h = outSvg ? parseFloat(outSvg.style.height) : 0;
    var valign = outSvg ? parseFloat(outSvg.style.verticalAlign) : 0;

    return {
      svg: holder.outerHTML,
      width: isFinite(w) ? w : 0,
      height: isFinite(h) ? h : 0,
      verticalAlign: isFinite(valign) ? valign : 0,
    };
  }

  global.__WECHAT_MATHJAX__ = { render: render };
})(typeof window !== 'undefined' ? window : globalThis);