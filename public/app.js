document.addEventListener('DOMContentLoaded', () => {
    // Cambio de pestañas (LIVE, MOVIES, SERIES)
    const tabs = document.querySelectorAll('.tab-btn');
    const contents = document.querySelectorAll('.tab-content');

    tabs.forEach(btn => {
        btn.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            contents.forEach(c => c.classList.remove('active'));

            btn.classList.add('active');
            const target = document.getElementById(btn.dataset.tab);
            if (target) target.classList.add('active');
        });
    });

    // Cargar datos dinámicos generados por el robot
    loadLiveData();
    loadMoviesData();
});

async function loadLiveData() {
    const container = document.getElementById('live-list');
    try {
        const res = await fetch('data/live.json');
        if (!res.ok) throw new Error('No hay canales generados aún.');
        const channels = await res.json();
        
        if (channels.length === 0) {
            container.innerHTML = '<p>No hay canales activos disponibles en este momento.</p>';
            return;
        }

        container.innerHTML = channels.map(ch => `
            <div class="card">
                <div class="card-info">
                    <h3>${ch.name}</h3>
                    <a href="${ch.url}" class="play-btn" target="_blank">Reproducir</a>
                </div>
            </div>
        `).join('');
    } catch (e) {
        container.innerHTML = '<p>Ejecutá el robot en GitHub Actions para compilar la lista de canales en vivo.</p>';
    }
}

async function loadMoviesData() {
    const container = document.getElementById('movies-list');
    try {
        const res = await fetch('data/movies.json');
        if (!res.ok) throw new Error('No hay películas generadas aún.');
        const movies = await res.json();

        if (movies.length === 0) {
            container.innerHTML = '<p>No hay películas disponibles.</p>';
            return;
        }

        container.innerHTML = movies.map(m => `
            <div class="card">
                <img src="${m.poster || ''}" alt="${m.title}">
                <div class="card-info">
                    <h3>${m.title}</h3>
                    <a href="${m.url}" class="play-btn" target="_blank">Ver Película</a>
                </div>
            </div>
        `).join('');
    } catch (e) {
        container.innerHTML = '<p>Ejecutá el robot en GitHub Actions para compilar el catálogo.</p>';
    }
}
