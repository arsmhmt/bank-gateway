// Toggle the side navigation
const sidebarToggle = document.body.querySelector('#sidebarToggle');
const sidebar = document.body.querySelector('#layoutSidenav_nav');
const content = document.body.querySelector('#layoutSidenav_content');

if (sidebarToggle) {
    // Toggle sidebar on button click
    sidebarToggle.addEventListener('click', event => {
        event.preventDefault();
        document.body.classList.toggle('sb-sidenav-toggled');
        localStorage.setItem('sb|sidebar-toggle', document.body.classList.contains('sb-sidenav-toggled'));
        
        // Toggle collapsed class on sidebar and content (if they exist)
        if (sidebar) sidebar.classList.toggle('collapsed');
        if (content) content.classList.toggle('collapsed');
    });

    // Check for saved preference
    if (localStorage.getItem('sb|sidebar-toggle') === 'true') {
        document.body.classList.add('sb-sidenav-toggled');
        if (sidebar) sidebar.classList.add('collapsed');
        if (content) content.classList.add('collapsed');
    }
}

// Close any open menu accordions when window is resized below 768px
window.addEventListener('resize', () => {
    if (window.innerWidth < 768) {
        const openDropdowns = document.querySelectorAll('.collapse.show');
        openDropdowns.forEach(dropdown => {
            const bsCollapse = new bootstrap.Collapse(dropdown, {
                toggle: false
            });
            bsCollapse.hide();
        });
    }
});

// Prevent the content wrapper from scrolling when the fixed side navigation is hovered over
const sidebarNav = document.querySelector('#layoutSidenav_nav');
if (sidebarNav) {
    sidebarNav.addEventListener('mousewheel', function(e) {
        const delta = Math.max(-1, Math.min(1, (e.wheelDelta || -e.detail)));
        this.scrollTop += (delta * 40); // Adjust scrolling speed
        e.preventDefault();
    });
}

// Initialize tooltips
const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
const tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
});

// Initialize popovers
const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
const popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
    return new bootstrap.Popover(popoverTriggerEl);
});

// Handle active state for sidebar items
const currentPath = window.location.pathname;
const sidebarLinks = document.querySelectorAll('.sb-sidenav-menu .nav-link');

sidebarLinks.forEach(link => {
    if (link.getAttribute('href') === currentPath) {
        link.classList.add('active');
        // Expand parent collapse if exists
        const parentCollapse = link.closest('.collapse');
        if (parentCollapse) {
            const bsCollapse = new bootstrap.Collapse(parentCollapse, {
                toggle: false
            });
            bsCollapse.show();
            
            // Update parent link attributes
            const parentLink = parentCollapse.previousElementSibling;
            if (parentLink && parentLink.classList.contains('collapsed')) {
                parentLink.classList.remove('collapsed');
                parentLink.setAttribute('aria-expanded', 'true');
            }
        }
    }
});

// Handle logout form submission
const logoutForm = document.querySelector('#logout-form');
if (logoutForm) {
    logoutForm.addEventListener('submit', function(e) {
        e.preventDefault();
        // Add any logout logic here if needed
        this.submit();
    });
}

// Search functionality
const searchInput = document.querySelector('.navbar-search input');
if (searchInput) {
    searchInput.addEventListener('keyup', function(e) {
        if (e.key === 'Enter') {
            const query = this.value.trim();
            if (query) {
                // Implement search functionality here
                console.log('Searching for:', query);
                // window.location.href = `/admin/search?q=${encodeURIComponent(query)}`;
            }
        }
    });
}

// Initialize dropdown menus
const dropdownElementList = [].slice.call(document.querySelectorAll('.dropdown-toggle'));
const dropdownList = dropdownElementList.map(function (dropdownToggleEl) {
    return new bootstrap.Dropdown(dropdownToggleEl);
});

// Handle sidebar toggle for mobile
const sidebarToggleTop = document.querySelector('#sidebarToggleTop');
if (sidebarToggleTop) {
    sidebarToggleTop.addEventListener('click', function() {
        document.body.classList.toggle('sidebar-toggled');
        sidebar.classList.toggle('toggled');
        
        if (sidebar.classList.contains('toggled')) {
            const collapseElementList = [].slice.call(document.querySelectorAll('.sidebar .collapse'));
            collapseElementList.forEach(collapseElement => {
                const bsCollapse = bootstrap.Collapse.getInstance(collapseElement);
                if (bsCollapse) {
                    bsCollapse.hide();
                }
            });
        }
    });
}

// Close dropdown when clicking outside
document.addEventListener('click', function(event) {
    const isClickInside = event.target.closest('.dropdown');
    if (!isClickInside) {
        const openDropdowns = document.querySelectorAll('.dropdown-menu.show');
        openDropdowns.forEach(dropdown => {
            const bsDropdown = bootstrap.Dropdown.getInstance(dropdown);
            if (bsDropdown) {
                bsDropdown.hide();
            }
        });
    }
});
