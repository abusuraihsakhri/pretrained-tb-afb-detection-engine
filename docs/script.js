(() => {
  const root = document.documentElement;
  const themeButton = document.querySelector('.theme-button');
  const menuButton = document.querySelector('.menu-button');
  const navigation = document.querySelector('#primary-navigation');
  const storedTheme = localStorage.getItem('tb-afb-theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

  function setTheme(theme) {
    root.dataset.theme = theme;
    const dark = theme === 'dark';
    themeButton.setAttribute('aria-pressed', String(dark));
    themeButton.setAttribute('aria-label', dark ? 'Use light theme' : 'Use dark theme');
  }

  setTheme(storedTheme || (prefersDark ? 'dark' : 'light'));

  themeButton.addEventListener('click', () => {
    const nextTheme = root.dataset.theme === 'dark' ? 'light' : 'dark';
    setTheme(nextTheme);
    localStorage.setItem('tb-afb-theme', nextTheme);
  });

  menuButton.addEventListener('click', () => {
    const open = menuButton.getAttribute('aria-expanded') !== 'true';
    menuButton.setAttribute('aria-expanded', String(open));
    navigation.dataset.open = String(open);
  });

  navigation.addEventListener('click', (event) => {
    if (event.target.closest('a')) {
      menuButton.setAttribute('aria-expanded', 'false');
      navigation.dataset.open = 'false';
    }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && navigation.dataset.open === 'true') {
      navigation.dataset.open = 'false';
      menuButton.setAttribute('aria-expanded', 'false');
      menuButton.focus();
    }
  });
})();
