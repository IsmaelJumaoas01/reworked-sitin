document.addEventListener('DOMContentLoaded', function() {
    // Sidebar Toggle
    const toggleBtn = document.querySelector('.toggle-sidebar');
    const sidebar = document.querySelector('.sidebar');
    const mainContent = document.querySelector('.main-content');
    const mainHeader = document.querySelector('.main-header');

    if (toggleBtn) {
        toggleBtn.addEventListener('click', function() {
            sidebar.classList.toggle('active');
            document.body.classList.toggle('sidebar-active');
        });
    }

    // Close sidebar when clicking outside on mobile
    document.addEventListener('click', function(e) {
        if (window.innerWidth <= 768) {
            if (!sidebar.contains(e.target) && !toggleBtn.contains(e.target) && sidebar.classList.contains('active')) {
                sidebar.classList.remove('active');
                document.body.classList.remove('sidebar-active');
            }
        }
    });

    // Card Animations
    const cards = document.querySelectorAll('.card');
    const animateCards = () => {
        cards.forEach(card => {
            const cardTop = card.getBoundingClientRect().top;
            const cardBottom = card.getBoundingClientRect().bottom;
            
            if (cardTop < window.innerHeight && cardBottom > 0) {
                card.classList.add('animate');
            }
        });
    };

    // Initial check for visible cards
    animateCards();

    // Animate cards on scroll
    window.addEventListener('scroll', animateCards);

    // Dropdown functionality
    const dropdownToggles = document.querySelectorAll('.dropdown-toggle');
    dropdownToggles.forEach(toggle => {
        toggle.addEventListener('click', function(e) {
            e.preventDefault();
            const dropdown = this.nextElementSibling;
            dropdown.classList.toggle('show');

            // Close other dropdowns
            dropdownToggles.forEach(otherToggle => {
                if (otherToggle !== toggle) {
                    otherToggle.nextElementSibling.classList.remove('show');
                }
            });
        });
    });

    // Close dropdowns when clicking outside
    document.addEventListener('click', function(e) {
        dropdownToggles.forEach(toggle => {
            const dropdown = toggle.nextElementSibling;
            if (!toggle.contains(e.target) && !dropdown.contains(e.target)) {
                dropdown.classList.remove('show');
            }
        });
    });

    // Alert dismissal
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        const dismissBtn = alert.querySelector('.btn-close');
        if (dismissBtn) {
            dismissBtn.addEventListener('click', function() {
                alert.classList.add('fade-out');
                setTimeout(() => {
                    alert.remove();
                }, 300);
            });
        }
    });

    // Add fade-in animation to main content on page load
    const contentWrapper = document.querySelector('.content-wrapper');
    if (contentWrapper) {
        contentWrapper.classList.add('fade-in');
    }

    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Add smooth scrolling to all links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href !== '#') {
                e.preventDefault();
                const target = document.querySelector(href);
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth'
                    });
                }
            }
        });
    });
}); 