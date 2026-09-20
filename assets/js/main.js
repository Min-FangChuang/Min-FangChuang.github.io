(() => {
  const toggle = document.querySelector('[data-nav-toggle]');
  const nav = document.querySelector('[data-nav]');

  if (toggle && nav) {
    toggle.addEventListener('click', () => {
      const open = toggle.getAttribute('aria-expanded') === 'true';
      toggle.setAttribute('aria-expanded', String(!open));
      toggle.setAttribute('aria-label', open ? '開啟導覽' : '關閉導覽');
      nav.classList.toggle('is-open', !open);
    });

    nav.addEventListener('click', (event) => {
      if (event.target.closest('a')) {
        toggle.setAttribute('aria-expanded', 'false');
        toggle.setAttribute('aria-label', '開啟導覽');
        nav.classList.remove('is-open');
      }
    });
  }

  const filterButtons = [...document.querySelectorAll('[data-filter]')];
  const projectTiles = [...document.querySelectorAll('[data-categories]')];
  const resultCount = document.querySelector('[data-result-count]');
  const emptyState = document.querySelector('[data-empty-state]');

  filterButtons.forEach((button) => {
    button.addEventListener('click', () => {
      const selected = button.dataset.filter;
      let visibleCount = 0;

      filterButtons.forEach((candidate) => {
        const active = candidate === button;
        candidate.classList.toggle('is-active', active);
        candidate.setAttribute('aria-pressed', String(active));
      });

      projectTiles.forEach((tile) => {
        const categories = tile.dataset.categories.split(/\s+/);
        const visible = selected === 'all' || categories.includes(selected);
        tile.hidden = !visible;
        tile.classList.toggle('is-hidden', !visible);
        if (visible) visibleCount += 1;
      });

      if (resultCount) resultCount.textContent = String(visibleCount);
      if (emptyState) emptyState.hidden = visibleCount !== 0;
    });
  });

  const projectModal = document.querySelector('[data-project-modal]');
  let lastProjectTrigger = null;
  let pageScrollPosition = 0;

  const lockPageScroll = () => {
    pageScrollPosition = window.scrollY;
    document.documentElement.classList.add('modal-open');
    document.body.classList.add('modal-open');
    document.body.style.top = `-${pageScrollPosition}px`;
  };

  const unlockPageScroll = () => {
    document.documentElement.classList.remove('modal-open');
    document.body.classList.remove('modal-open');
    document.body.style.removeProperty('top');
    window.scrollTo(0, pageScrollPosition);
  };

  if (projectModal) {
    const modalImage = projectModal.querySelector('[data-modal-image]');
    const modalCategory = projectModal.querySelector('[data-modal-category]');
    const modalTitle = projectModal.querySelector('[data-modal-title]');
    const modalSummary = projectModal.querySelector('[data-modal-summary]');
    const modalPoints = projectModal.querySelector('[data-modal-points]');
    const modalTags = projectModal.querySelector('[data-modal-tags]');
    const modalStatus = projectModal.querySelector('[data-modal-status]');
    const modalMore = projectModal.querySelector('[data-modal-more]');
    const modalDemos = projectModal.querySelector('[data-modal-demos]');

    document.querySelectorAll('[data-project]').forEach((button) => {
      button.addEventListener('click', () => {
        const source = document.querySelector(`#project-${button.dataset.project}`);
        if (!source) return;

        lastProjectTrigger = button;
        modalImage.src = source.dataset.image;
        modalImage.alt = source.dataset.imageAlt;
        modalCategory.textContent = source.dataset.category;
        modalTitle.textContent = source.dataset.title;
        modalSummary.textContent = source.dataset.summary;
        modalStatus.textContent = source.dataset.status;

        modalPoints.replaceChildren(...source.dataset.points.split('|').map((point) => {
          const item = document.createElement('li');
          item.textContent = point;
          return item;
        }));

        modalTags.replaceChildren(...source.dataset.tags.split('|').map((tag) => {
          const chip = document.createElement('span');
          chip.textContent = tag;
          return chip;
        }));

        if (source.dataset.more) {
          modalMore.hidden = false;
          modalMore.href = source.dataset.more;
          modalMore.textContent = source.dataset.moreLabel || '了解更多';
          modalMore.target = source.dataset.more.endsWith('.pdf') ? '_blank' : '';
        } else {
          modalMore.hidden = true;
          modalMore.removeAttribute('href');
          modalMore.removeAttribute('target');
        }

        const demoEntries = source.dataset.demos
          ? source.dataset.demos.split('|').map((entry) => {
            const [label, url] = entry.split('::');
            return { label, url };
          })
          : source.dataset.demo
            ? [{ label: source.dataset.demoLabel || '觀看 Demo ↗', url: source.dataset.demo }]
            : [];

        modalDemos.replaceChildren(...demoEntries.map(({ label, url }) => {
          const link = document.createElement('a');
          link.className = 'button button-secondary';
          link.href = url;
          link.target = '_blank';
          link.rel = 'noreferrer';
          link.textContent = label.endsWith('↗') ? label : `${label} ↗`;
          return link;
        }));

        lockPageScroll();
        projectModal.showModal();
      });
    });

    projectModal.querySelectorAll('[data-project-close]').forEach((button) => {
      button.addEventListener('click', () => projectModal.close());
    });

    projectModal.addEventListener('click', (event) => {
      if (event.target === projectModal) projectModal.close();
    });

    projectModal.addEventListener('close', () => {
      unlockPageScroll();
      lastProjectTrigger?.focus();
    });
  }

  document.querySelectorAll('[data-evidence-gallery]').forEach((gallery) => {
    const mainButton = gallery.querySelector('[data-lightbox]');
    const mainImage = gallery.querySelector('[data-evidence-image]');
    const title = gallery.querySelector('[data-evidence-title]');
    const description = gallery.querySelector('[data-evidence-description]');
    const count = gallery.querySelector('[data-evidence-count]');
    const thumbs = [...gallery.querySelectorAll('[data-evidence-thumb]')];
    const filters = [...gallery.querySelectorAll('[data-evidence-filter]')];
    const prev = gallery.querySelector('[data-evidence-prev]');
    const next = gallery.querySelector('[data-evidence-next]');
    let activeGroup = filters.find((filter) => filter.classList.contains('is-active'))?.dataset.evidenceFilter || thumbs[0]?.dataset.group;
    let activeIndex = 0;

    const activeThumbs = () => thumbs.filter((thumb) => thumb.dataset.group === activeGroup);

    const showEvidence = (index) => {
      const visibleThumbs = activeThumbs();
      activeIndex = (index + visibleThumbs.length) % visibleThumbs.length;
      const active = visibleThumbs[activeIndex];
      const src = active.dataset.src;

      mainButton.dataset.lightbox = src;
      mainImage.src = src;
      mainImage.alt = active.dataset.alt;
      title.textContent = active.dataset.title;
      description.textContent = active.dataset.description;
      count.textContent = `${String(activeIndex + 1).padStart(2, '0')} / ${String(visibleThumbs.length).padStart(2, '0')}`;

      thumbs.forEach((thumb) => {
        const visible = thumb.dataset.group === activeGroup;
        const selected = thumb === active;
        thumb.hidden = !visible;
        thumb.classList.toggle('is-active', selected);
        thumb.setAttribute('aria-selected', String(selected));
      });

      active.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
    };

    thumbs.forEach((thumb) => {
      thumb.addEventListener('click', () => {
        activeGroup = thumb.dataset.group;
        showEvidence(activeThumbs().indexOf(thumb));
      });
    });

    filters.forEach((filter) => {
      filter.addEventListener('click', () => {
        activeGroup = filter.dataset.evidenceFilter;
        filters.forEach((candidate) => {
          const selected = candidate === filter;
          candidate.classList.toggle('is-active', selected);
          candidate.setAttribute('aria-pressed', String(selected));
        });
        showEvidence(0);
      });
    });

    prev?.addEventListener('click', () => showEvidence(activeIndex - 1));
    next?.addEventListener('click', () => showEvidence(activeIndex + 1));
    showEvidence(0);
  });

  document.querySelectorAll('[data-code-switcher]').forEach((switcher) => {
    const filters = [...switcher.querySelectorAll('[data-code-filter]')];
    const panels = [...switcher.querySelectorAll('[data-code-panel]')];

    const showPanel = (group) => {
      filters.forEach((filter) => {
        const selected = filter.dataset.codeFilter === group;
        filter.classList.toggle('is-active', selected);
        filter.setAttribute('aria-pressed', String(selected));
      });

      panels.forEach((panel) => {
        panel.hidden = panel.dataset.codePanel !== group;
        panel.classList.toggle('is-active', panel.dataset.codePanel === group);
      });
    };

    filters.forEach((filter) => {
      filter.addEventListener('click', () => showPanel(filter.dataset.codeFilter));
    });

    switcher.querySelectorAll('[data-copy-code]').forEach((button) => {
      button.addEventListener('click', async () => {
        const panel = button.closest('[data-code-panel]');
        const code = panel?.querySelector('code')?.textContent.trim();
        if (!code) return;

        try {
          await navigator.clipboard.writeText(code);
          button.textContent = '已複製';
          window.setTimeout(() => {
            button.textContent = '複製';
          }, 1400);
        } catch {
          button.textContent = '複製失敗';
          window.setTimeout(() => {
            button.textContent = '複製';
          }, 1400);
        }
      });
    });

    const initial = filters.find((filter) => filter.classList.contains('is-active'))?.dataset.codeFilter || panels[0]?.dataset.codePanel;
    if (initial) showPanel(initial);
  });

  document.querySelectorAll('[data-youtube-embed]').forEach((embed) => {
    const frameWrap = embed.querySelector('[data-youtube-frame]');
    const fallback = embed.querySelector('[data-youtube-fallback]');
    const videoId = embed.dataset.videoId;

    if (!frameWrap || !fallback || !videoId || location.protocol === 'file:') return;

    const iframe = document.createElement('iframe');
    iframe.src = `https://www.youtube-nocookie.com/embed/${videoId}?playsinline=1&rel=0`;
    iframe.title = 'ESP32 智慧開關與冷氣紅外線控制 Demo';
    iframe.loading = 'lazy';
    iframe.referrerPolicy = 'strict-origin-when-cross-origin';
    iframe.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share';
    iframe.allowFullscreen = true;

    frameWrap.replaceChildren(iframe);
    frameWrap.hidden = false;
    fallback.hidden = true;
  });

  const dialog = document.querySelector('[data-lightbox-dialog]');
  const image = dialog?.querySelector('[data-lightbox-image]');
  const close = dialog?.querySelector('[data-lightbox-close]');

  if (dialog && image) {
    document.querySelectorAll('[data-lightbox]').forEach((button) => {
      button.addEventListener('click', () => {
        image.src = button.dataset.lightbox;
        image.alt = button.querySelector('img')?.alt || '放大圖片';
        dialog.showModal();
      });
    });

    close?.addEventListener('click', () => dialog.close());
    dialog.addEventListener('click', (event) => {
      if (event.target === dialog) dialog.close();
    });
  }
})();
