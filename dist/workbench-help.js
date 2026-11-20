/* Explanations stay with the control they describe, including inside modal dialogs. */
(() => {
  const triggerSelector = 'button.help-trigger[aria-describedby]';
  const word = document.createElement('span');
  word.id = 'workbenchHelpWord';
  word.hidden = true;
  word.dataset.ownI18n = '';
  document.body.append(word);
  function language() {
    word.textContent = document.documentElement.lang.startsWith('en') ? 'Help' : '說明';
  }
  language();

  let trigger = null, tip = null, marker = null, point = null, timer, exitTimer;
  function hide() {
    clearTimeout(timer);
    clearTimeout(exitTimer);
    if (tip) {
      if (tip.isConnected) tip.hidePopover?.();
      tip.hidden = true;
      if (marker) marker.replaceWith(tip);
    }
    trigger = tip = marker = point = null;
  }
  function helpAt(node) {
    const group = node?.closest?.('.help-heading') ||
      node?.labels?.[0]?.closest('.help-heading');
    return node?.closest?.(triggerSelector) || group?.querySelector(triggerSelector);
  }
  function show(button) {
    if (!button.isConnected || !button.getClientRects().length || button.closest('[inert]')) return hide();
    const note = document.getElementById(button.getAttribute('aria-describedby'));
    if (!note?.textContent.trim()) return hide();
    tip = note;
    tip.setAttribute('popover', 'manual');
    if (!tip.showPopover) {
      marker = document.createComment('help');
      tip.replaceWith(marker);
      (button.closest('dialog[open]') || document.body).append(tip);
    }
    tip.hidden = false;
    tip.showPopover?.();
    const rect = button.getBoundingClientRect(), size = tip.getBoundingClientRect();
    const top = rect.bottom + 4 + size.height <= innerHeight - 8
      ? rect.bottom + 4 : rect.top - size.height - 4;
    tip.style.left = Math.max(8, Math.min(rect.left, innerWidth - size.width - 8)) + 'px';
    tip.style.top = Math.max(8, Math.min(top, innerHeight - size.height - 8)) + 'px';
  }
  function schedule(button) {
    clearTimeout(exitTimer);
    if (button === trigger) return;
    hide();
    trigger = button;
    timer = setTimeout(() => show(button), 600);
  }
  document.addEventListener('pointerover', event => {
    if (event.pointerType === 'touch' || event.buttons) return;
    if (tip?.contains(event.target)) return clearTimeout(exitTimer);
    const button = helpAt(event.target);
    if (button) schedule(button);
  });
  document.addEventListener('pointermove', event => {
    if (!trigger || tip || event.pointerType === 'touch' || event.buttons) return;
    if (helpAt(event.target) !== trigger) return;
    if (point && point.x === event.clientX && point.y === event.clientY) return;
    point = {x:event.clientX, y:event.clientY};
    clearTimeout(timer);
    const button = trigger;
    timer = setTimeout(() => show(button), 600);
  });
  document.addEventListener('pointerout', event => {
    if (event.pointerType === 'touch' || !trigger) return;
    if (helpAt(event.relatedTarget) === trigger || tip?.contains(event.relatedTarget)) return;
    if (helpAt(event.target) === trigger || tip?.contains(event.target)) {
      if (!tip) hide();
      else exitTimer = setTimeout(hide, 140);
    }
  });
  document.addEventListener('focusin', event => {
    const button = helpAt(event.target);
    if (button) schedule(button);
  });
  document.addEventListener('focusout', event => {
    if (trigger && helpAt(event.target) === trigger && !tip?.contains(event.relatedTarget)) hide();
  });
  document.addEventListener('pointerdown', event => {
    if (trigger && !trigger.contains(event.target) && !tip?.contains(event.target)) hide();
  }, true);
  document.addEventListener('click', event => {
    const button = event.target.closest(triggerSelector);
    if (!button) return;
    const wasOpen = button === trigger && tip;
    hide();
    if (!wasOpen) { trigger = button; show(button); }
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && trigger) {
      const wasOpen = Boolean(tip);
      hide();
      if (wasOpen) {
        event.preventDefault();
        event.stopPropagation();
      }
    }
  }, true);
  document.addEventListener('scroll', event => {
    if (trigger && !tip?.contains(event.target)) hide();
  }, true);
  document.addEventListener('close', hide, true);
  document.addEventListener('input', hide);
  window.addEventListener('resize', hide);
  window.addEventListener('blur', hide);
  window.addEventListener('atlas-language', () => { hide(); language(); });
})();
