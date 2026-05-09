/* =====================================================
   クレジットカード比較ナビ 共通スクリプト
   ===================================================== */

/* ===== モバイルTOC 折り畳み ===== */
(function(){
  var title = document.querySelector('.toc-box-title');
  var list  = document.querySelector('.toc-list');
  if (!title || !list) return;

  function isMobile(){ return window.innerWidth <= 768; }

  function initToc(){
    if (isMobile()) {
      list.classList.remove('open');
    } else {
      list.classList.add('open');
    }
  }

  title.addEventListener('click', function(){
    list.classList.toggle('open');
    title.classList.toggle('open');
  });

  initToc();
  window.addEventListener('resize', initToc);
})();

/* =====================================================
   GA4 カスタムイベント計測
   - affiliate_click  : A8アフィリエイトリンクのクリック
   - outbound_click   : 自サイト外への外部リンククリック（A8以外）
   - internal_link_click : サイト内 articles/* / pillar* / cards/* リンク
   - scroll_depth     : 25/50/75/90% スクロール到達
   ===================================================== */
(function(){
  if (typeof window.gtag !== 'function') return;
  var SITE_HOST = location.hostname;

  function getLinkInfo(a){
    var href = a.getAttribute('href') || '';
    var text = (a.textContent || '').trim().slice(0, 80);
    return { href: href, text: text };
  }

  /* === クリックイベント計測（イベント委譲） === */
  document.addEventListener('click', function(e){
    var a = e.target.closest && e.target.closest('a');
    if (!a) return;
    var info = getLinkInfo(a);
    var href = info.href;
    if (!href || href.charAt(0) === '#') return;

    var pagePath = location.pathname;

    // 1. A8 アフィリエイトリンク（最優先）
    if (href.indexOf('px.a8.net') !== -1) {
      try {
        gtag('event', 'affiliate_click', {
          link_url: href,
          link_text: info.text,
          page_path: pagePath,
          affiliate_network: 'a8'
        });
      } catch(_){}
      return;
    }

    // 2. 外部リンク（http(s)で別ドメイン）
    if (/^https?:\/\//.test(href)) {
      try {
        var u = new URL(href);
        if (u.hostname && u.hostname !== SITE_HOST) {
          gtag('event', 'outbound_click', {
            link_url: href,
            link_text: info.text,
            link_host: u.hostname,
            page_path: pagePath
          });
          return;
        }
      } catch(_){}
    }

    // 3. 内部リンク（記事・ピラーへの遷移）
    if (href.indexOf('/articles/') === 0 || href.indexOf('articles/') === 0) {
      try {
        gtag('event', 'internal_link_click', {
          link_url: href,
          link_text: info.text,
          target_path: href,
          page_path: pagePath
        });
      } catch(_){}
    }
  }, { passive: true });

  /* === スクロール深度（25/50/75/90） === */
  var fired = { 25:false, 50:false, 75:false, 90:false };
  function onScroll(){
    var doc = document.documentElement;
    var sh = doc.scrollHeight - doc.clientHeight;
    if (sh <= 0) return;
    var pct = Math.min(100, Math.max(0, Math.floor((window.scrollY || doc.scrollTop) / sh * 100)));
    [25,50,75,90].forEach(function(t){
      if (!fired[t] && pct >= t) {
        fired[t] = true;
        try {
          gtag('event', 'scroll_depth', {
            percent: t,
            page_path: location.pathname
          });
        } catch(_){}
      }
    });
  }
  var scrollTimer = null;
  window.addEventListener('scroll', function(){
    if (scrollTimer) return;
    scrollTimer = setTimeout(function(){
      scrollTimer = null;
      onScroll();
    }, 200);
  }, { passive: true });
})();
