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

    // Handling Ticketing System
    document.getElementById('ticketSubmit').addEventListener('click', async () => {
        const category = document.getElementById('ticketCategory').value;
        const subject  = document.getElementById('ticketSubject').value.trim();
        const body     = document.getElementById('ticketBody').value.trim();
        const errorDiv = document.getElementById('ticketError');

        if (!category || !subject || !body) {
            errorDiv.textContent = 'يرجى ملء جميع الحقول.';
            errorDiv.classList.remove('d-none');
            return;
        }

        errorDiv.classList.add('d-none');
        document.getElementById('ticketSubmit').disabled = true;

        const formData = new FormData();
        const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
        formData.append('csrfmiddlewaretoken', csrfToken);
        formData.append('category', category);
        formData.append('subject', subject);
        formData.append('body', body);

        try {
            const submitUrl = document.querySelector('[data-submit-url]').dataset.submitUrl;

            const response = await fetch(submitUrl, {
            method: 'POST',
            body: formData,
            });


            if (response.ok) {
                document.getElementById('ticketForm').classList.add('d-none');
                document.getElementById('ticketSuccess').classList.remove('d-none');
            } else {
                throw new Error();
            }
        } catch {
            errorDiv.textContent = 'حدث خطأ، يرجى المحاولة مرة أخرى.';
            errorDiv.classList.remove('d-none');
            document.getElementById('ticketSubmit').disabled = false;
        }
    });

    // reset modal when closed
    document.getElementById('supportModal').addEventListener('hidden.bs.modal', () => {
        document.getElementById('ticketForm').classList.remove('d-none');
        document.getElementById('ticketSuccess').classList.add('d-none');
        document.getElementById('ticketError').classList.add('d-none');
        document.getElementById('ticketCategory').value = '';
        document.getElementById('ticketSubject').value = '';
        document.getElementById('ticketBody').value = '';
        document.getElementById('ticketSubmit').disabled = false;
    });
});

function toggleTheme(theme){    let body = document.getElementById('body');
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