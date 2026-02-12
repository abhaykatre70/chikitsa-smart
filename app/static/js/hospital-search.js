function initHospitalSearch(config) {
    const input = document.getElementById(config.inputId);
    const results = document.getElementById(config.resultsId);
    const hidden = document.getElementById(config.hiddenId);
    const stateInput = config.stateId ? document.getElementById(config.stateId) : null;
    const districtInput = config.districtId ? document.getElementById(config.districtId) : null;

    if (!input || !results || !hidden) return;

    async function fetchHospitals(query) {
        const params = new URLSearchParams();
        params.set('q', query);
        params.set('gov_only', '1');
        if (stateInput && stateInput.value.trim()) {
            params.set('state', stateInput.value.trim());
        }
        if (districtInput && districtInput.value.trim()) {
            params.set('district', districtInput.value.trim());
        }
        const response = await fetch(`/api/hospitals?${params.toString()}`);
        if (!response.ok) return [];
        return response.json();
    }

    function clearResults() {
        results.innerHTML = '';
    }

    function renderResults(items) {
        clearResults();
        items.forEach((item) => {
            const li = document.createElement('li');
            li.textContent = `${item.name} (${item.district || 'Unknown'}, ${item.state || 'Unknown'})`;
            li.dataset.id = item.id;
            li.dataset.name = item.name;
            results.appendChild(li);
        });
    }

    input.addEventListener('input', async () => {
        const value = input.value.trim();
        hidden.value = '';
        if (value.length < 2) {
            clearResults();
            return;
        }
        const items = await fetchHospitals(value);
        renderResults(items);
    });

    results.addEventListener('click', (event) => {
        const target = event.target.closest('li');
        if (!target) return;
        input.value = target.dataset.name;
        hidden.value = target.dataset.id;
        clearResults();
    });

    document.addEventListener('click', (event) => {
        if (!results.contains(event.target) && event.target !== input) {
            clearResults();
        }
    });
}
