// Generic error modal + AJAX error handling for all pages in data_visualization

(function(){
  function ensureModal(){
    if(document.getElementById('errModalOverlay')) return;
    const overlay = document.createElement('div');
    overlay.id = 'errModalOverlay';
    overlay.className = 'err-modal-overlay';
    overlay.innerHTML = (
      '<div class="err-modal" role="dialog" aria-modal="true" aria-labelledby="errModalTitle">'
      + '<div class="err-modal-header">'
      + '<h3 id="errModalTitle" class="err-modal-title">Error</h3>'
      + '<button type="button" id="errModalClose" class="err-modal-close" aria-label="Close">×</button>'
      + '</div>'
      + '<div id="errModalBody" class="err-modal-body"></div>'
      + '<div class="err-modal-footer">'
      + '<button type="button" id="errModalOk" class="err-modal-btn">OK</button>'
      + '</div>'
      + '</div>'
    );
    document.body.appendChild(overlay);
    const hide = () => overlay.style.display = 'none';
    document.getElementById('errModalClose').addEventListener('click', hide);
    document.getElementById('errModalOk').addEventListener('click', hide);
    overlay.addEventListener('click', (e)=>{ if(e.target===overlay) hide(); });
    document.addEventListener('keydown',(e)=>{ if(e.key==='Escape') hide(); });
  }

  function showError(message){
    ensureModal();
    const overlay = document.getElementById('errModalOverlay');
    const body = document.getElementById('errModalBody');
    body.textContent = message || 'An error occurred.';
    overlay.style.display = 'flex';
  }

  async function submitFormAjax(form){
    const formData = new FormData(form);
    const params = new URLSearchParams(formData);
    const method = (form.getAttribute('method') || 'GET').toUpperCase();
    const action = form.getAttribute('action') || window.location.pathname;
    const url = method==='GET' ? `${action}?${params.toString()}` : action;

    const resp = await fetch(url, {
      method,
      headers: {'X-Requested-With':'XMLHttpRequest','Accept':'application/json'},
      body: method==='GET' ? undefined : params
    });

    if(!resp.ok){
      let msg = `Request failed (${resp.status})`;
      try {
        const data = await resp.json();
        if(data && (data.error_message || data.message)){
          msg = data.error_message || data.message;
        }
      } catch(_){ /* ignore */ }
      showError(msg);
      return false;
    }

    if(method==='GET'){
      // Keep UX consistent: update URL and reload to refresh charts/context
      window.location.search = params.toString();
    } else {
      window.location.reload();
    }
    return true;
  }

  document.addEventListener('DOMContentLoaded', ()=>{
    // Wire all GET forms by default
    document.querySelectorAll('form[method="get"], form:not([method])').forEach((form)=>{
      if(form.dataset.errBound==='true') return;
      form.dataset.errBound='true';
      form.addEventListener('submit', async (e)=>{
        e.preventDefault();
        try { await submitFormAjax(form); } catch(_){ showError('Unexpected error'); }
      });
    });

    // If server rendered error, show it immediately without changing the screen
    if(window.errorMessage){ showError(window.errorMessage); }
  });

  // expose in case manual call is needed
  window.showErrorModal = showError;
})();


