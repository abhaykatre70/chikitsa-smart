function initHospitalDropdowns(config) {
    const stateSelect = document.getElementById(config.stateId);
    const districtSelect = document.getElementById(config.districtId);
    const hospitalSelect = document.getElementById(config.hospitalId);

    if (!stateSelect || !districtSelect || !hospitalSelect) return;

    async function fetchJSON(url) {
        const response = await fetch(url);
        if (!response.ok) return [];
        return response.json();
    }

    function fillSelect(select, items, placeholder) {
        select.innerHTML = '';
        const option = document.createElement('option');
        option.value = '';
        option.textContent = placeholder;
        select.appendChild(option);

        items.forEach((item) => {
            const opt = document.createElement('option');
            opt.value = item.value ?? item;
            opt.textContent = item.label ?? item;
            select.appendChild(opt);
        });
    }

    async function loadStates() {
        const states = await fetchJSON('/api/hospital-states?gov_only=1');
        if (!states.length) {
            fillSelect(stateSelect, [], 'No data available');
            stateSelect.disabled = true;
            return;
        }
        fillSelect(stateSelect, states, 'Select State');
        stateSelect.disabled = false;
    }

    async function loadDistricts(state) {
        districtSelect.disabled = true;
        hospitalSelect.disabled = true;
        fillSelect(districtSelect, [], 'Select District');
        fillSelect(hospitalSelect, [], 'Select Hospital');

        if (!state) {
            return;
        }

        const districts = await fetchJSON(`/api/hospital-districts?gov_only=1&state=${encodeURIComponent(state)}`);
        fillSelect(districtSelect, districts, 'Select District');
        districtSelect.disabled = false;

        if (districts.length) {
            districtSelect.selectedIndex = 1;
            await loadHospitals(state, districtSelect.value);
        } else {
            await loadHospitals(state, '');
        }
    }

    async function loadHospitals(state, district) {
        hospitalSelect.disabled = true;
        fillSelect(hospitalSelect, [], 'Select Hospital');

        if (!state && !district) {
            hospitalSelect.disabled = false;
            return;
        }

        const query = new URLSearchParams();
        query.set('gov_only', '1');
        if (state) query.set('state', state);
        if (district) query.set('district', district);
        query.set('limit', '2000');

        const hospitals = await fetchJSON(`/api/hospital-list?${query.toString()}`);
        const items = hospitals.map((hospital) => ({
            value: hospital.id,
            label: `${hospital.name} (${hospital.district || 'Unknown'}, ${hospital.state || 'Unknown'})`,
        }));
        fillSelect(hospitalSelect, items, 'Select Hospital');
        hospitalSelect.disabled = false;
    }

    stateSelect.addEventListener('change', async () => {
        const state = stateSelect.value;
        await loadDistricts(state);
    });

    districtSelect.addEventListener('change', async () => {
        const state = stateSelect.value;
        const district = districtSelect.value;
        await loadHospitals(state, district);
    });

    loadStates();
}
