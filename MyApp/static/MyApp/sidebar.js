// BGNU Platform Universal Controller (Collapsible Sidebar, Dark Mode, Notifications, PWA)
(function() {
    // 1. Initialize Theme (Dark Mode / Light Mode) early to prevent flash
    const savedTheme = localStorage.getItem('bgnu_theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);

    function initPlatformFeatures() {
        // --- A. Collapsible Sidebar ---
        const sidebar = document.getElementById('appSidebar');
        const toggleBtn = document.getElementById('sidebarToggle');
        const backdrop = document.getElementById('sidebarBackdrop');

        if (sidebar && window.innerWidth > 1024) {
            if (localStorage.getItem('bgnu_sidebar_collapsed') === 'true') {
                sidebar.classList.add('is-collapsed');
                if (toggleBtn) toggleBtn.setAttribute('title', 'Show Navigation');
            } else {
                if (toggleBtn) toggleBtn.setAttribute('title', 'Hide Navigation');
            }
        }

        if (toggleBtn && sidebar) {
            toggleBtn.onclick = function(e) {
                e.preventDefault();
                if (window.innerWidth > 1024) {
                    const isCollapsed = sidebar.classList.toggle('is-collapsed');
                    localStorage.setItem('bgnu_sidebar_collapsed', isCollapsed ? 'true' : 'false');
                    toggleBtn.setAttribute('title', isCollapsed ? 'Show Navigation' : 'Hide Navigation');
                } else {
                    const isOpen = sidebar.classList.toggle('open');
                    sidebar.classList.toggle('is-open', isOpen);
                    if (backdrop) {
                        backdrop.classList.toggle('open', isOpen);
                        backdrop.classList.toggle('is-visible', isOpen);
                    }
                }
            };
        }

        if (backdrop && sidebar) {
            backdrop.onclick = function() {
                sidebar.classList.remove('open');
                sidebar.classList.remove('is-open');
                backdrop.classList.remove('open');
                backdrop.classList.remove('is-visible');
            };
        }

        // --- B. Dark Mode Toggle ---
        const themeBtn = document.getElementById('themeToggleBtn');
        function updateThemeIcon() {
            const current = document.documentElement.getAttribute('data-theme');
            if (themeBtn) {
                themeBtn.textContent = current === 'dark' ? '☀️' : '🌙';
                themeBtn.setAttribute('title', current === 'dark' ? 'Switch to Light Theme' : 'Switch to Dark Mode');
            }
        }
        updateThemeIcon();

        if (themeBtn) {
            themeBtn.onclick = function(e) {
                e.preventDefault();
                const current = document.documentElement.getAttribute('data-theme');
                const next = current === 'dark' ? 'light' : 'dark';
                document.documentElement.setAttribute('data-theme', next);
                localStorage.setItem('bgnu_theme', next);
                updateThemeIcon();
            };
        }

        // --- C. Notifications Dropdown ---
        const notifBtn = document.getElementById('notifToggleBtn');
        const notifDropdown = document.getElementById('notifDropdown');

        if (notifBtn && notifDropdown) {
            notifBtn.onclick = function(e) {
                e.stopPropagation();
                notifDropdown.classList.toggle('show');
            };

            document.addEventListener('click', function(e) {
                if (!notifDropdown.contains(e.target) && e.target !== notifBtn) {
                    notifDropdown.classList.remove('show');
                }
            });
        }

        // --- D. Register PWA Service Worker ---
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/static/MyApp/sw.js').catch(function(err) {
                // Silently ignore if in dev environment
            });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPlatformFeatures);
    } else {
        initPlatformFeatures();
    }
})();
