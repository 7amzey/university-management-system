document.addEventListener('DOMContentLoaded', () =>{
    let body = document.getElementById('body');
    let theme = localStorage.getItem('theme') || 'light';
    toggleTheme(theme);
    document.addEventListener('shown.bs.collapse', e => {
        document.querySelectorAll(`[data-bs-target="#${e.target.id}"] .bi-chevron-down`)
            .forEach(icon => icon.style.transform = 'rotate(180deg)');
    });
    document.addEventListener('hidden.bs.collapse', e => {
        document.querySelectorAll(`[data-bs-target="#${e.target.id}"] .bi-chevron-down`)
            .forEach(icon => icon.style.transform = 'rotate(0deg)');
    });

});

function toggleTheme(theme){
    let body = document.getElementById('body');
    if(theme === 'light'){
        localStorage.setItem('theme', 'light');
        body.setAttribute('data-bs-theme', 'light');
    }else{
        localStorage.setItem('theme', 'dark');
        body.setAttribute('data-bs-theme', 'dark');
    }
}

let collapsed = false;
function toggleDesktop() {
    collapsed = !collapsed;
    document.getElementById('desktopSidebar').classList.toggle('collapsed', collapsed);
    document.getElementById('main-content').classList.toggle('sidebar-collapsed', collapsed);
    document.getElementById('collapseIcon').className = collapsed
        ? 'bi bi-chevron-left flex-shrink-0'
        : 'bi bi-chevron-right flex-shrink-0';
}