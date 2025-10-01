// Mobile menu toggle
const mobileMenu = document.getElementById('mobile-menu');
const navMenu = document.getElementById('nav-menu');

if (mobileMenu && navMenu) {
    mobileMenu.addEventListener('click', function() {
        navMenu.classList.toggle('show');
        mobileMenu.classList.toggle('active');
    });
}

// Dropdown menu functionality for mobile
const dropdowns = document.querySelectorAll('.dropdown');

dropdowns.forEach(dropdown => {
    if (window.innerWidth <= 768) {
        const dropdownLink = dropdown.querySelector('a');

        dropdownLink.addEventListener('click', function(e) {
            if (window.innerWidth <= 768) {
                e.preventDefault();
                dropdown.classList.toggle('active');
            }
        });
    }
});

// Smooth scrolling for navigation links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();

        const targetId = this.getAttribute('href');
        if(targetId === '#') return;

        const targetElement = document.querySelector(targetId);
        if(targetElement) {
            // Close mobile menu if open
            if (navMenu && navMenu.classList.contains('show')) {
                navMenu.classList.remove('show');
                mobileMenu.classList.remove('active');
            }

            window.scrollTo({
                top: targetElement.offsetTop - 80,
                behavior: 'smooth'
            });
        }
    });
});

// Update dropdown behavior on window resize
window.addEventListener('resize', function() {
    dropdowns.forEach(dropdown => {
        const dropdownLink = dropdown.querySelector('a');

        // Remove existing event listeners
        const newDropdownLink = dropdownLink.cloneNode(true);
        dropdownLink.parentNode.replaceChild(newDropdownLink, dropdownLink);

        if (window.innerWidth <= 768) {
            newDropdownLink.addEventListener('click', function(e) {
                e.preventDefault();
                dropdown.classList.toggle('active');
            });
        }
    });
});