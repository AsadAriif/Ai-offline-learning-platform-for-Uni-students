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
                themeBtn.innerHTML = current === 'dark' ? '<svg width=\"16\" height=\"16\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><circle cx=\"12\" cy=\"12\" r=\"5\"></circle><line x1=\"12\" y1=\"1\" x2=\"12\" y2=\"3\"></line><line x1=\"12\" y1=\"21\" x2=\"12\" y2=\"23\"></line><line x1=\"4.22\" y1=\"4.22\" x2=\"5.64\" y2=\"5.64\"></line><line x1=\"18.36\" y1=\"18.36\" x2=\"19.78\" y2=\"19.78\"></line><line x1=\"1\" y1=\"12\" x2=\"3\" y2=\"12\"></line><line x1=\"21\" y1=\"12\" x2=\"23\" y2=\"12\"></line><line x1=\"4.22\" y1=\"19.78\" x2=\"5.64\" y2=\"18.36\"></line><line x1=\"18.36\" y1=\"5.64\" x2=\"19.78\" y2=\"4.22\"></line></svg>' : '<svg width=\"16\" height=\"16\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z\"></path></svg>';
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
