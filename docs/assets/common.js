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
