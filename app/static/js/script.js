const menu = document.querySelector('#menu-btn');
const navbar = document.querySelector('.navbar');

if (menu && navbar) {
    menu.addEventListener('click', () => {
        menu.classList.toggle('fa-times');
        navbar.classList.toggle('active');
    });

    window.addEventListener('scroll', () => {
        menu.classList.remove('fa-times');
        navbar.classList.remove('active');
    });
}

document.querySelectorAll('a[href^="#"]').forEach((link) => {
    link.addEventListener('click', (event) => {
        const hash = link.getAttribute('href');
        if (!hash || hash === '#') return;
        const target = document.querySelector(hash);
        if (!target) return;
        event.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
});
