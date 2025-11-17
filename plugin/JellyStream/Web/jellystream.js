let allSeries = [];
let currentSite = 'aniworld';
let searchTimeout = null;

function getAuthHeaders() {
    // Try multiple ways to get the auth token
    let token = null;

    // Method 1: Check window.ApiClient
    if (window.ApiClient && typeof window.ApiClient.accessToken === 'function') {
        token = window.ApiClient.accessToken();
    }

    // Method 2: Check parent window
    if (!token && window.parent && window.parent.ApiClient && typeof window.parent.ApiClient.accessToken === 'function') {
        token = window.parent.ApiClient.accessToken();
    }

    // Method 3: Check localStorage (Jellyfin stores tokens here)
    if (!token) {
        try {
            const credentials = localStorage.getItem('jellyfin_credentials');
            if (credentials) {
                const parsed = JSON.parse(credentials);
                if (parsed && parsed.Servers && parsed.Servers.length > 0) {
                    token = parsed.Servers[0].AccessToken;
                }
            }
        } catch (e) {
            console.error('Failed to get token from localStorage:', e);
        }
    }

    if (token) {
        return { 'X-Emby-Token': token };
    }

    console.warn('No auth token found');
    return {};
}

document.addEventListener('DOMContentLoaded', () => {
    const siteSelect = document.getElementById('siteSelect');
    const searchInput = document.getElementById('searchInput');
    const refreshBtn = document.getElementById('refreshBtn');

    siteSelect.addEventListener('change', (e) => {
        currentSite = e.target.value;
        loadSeriesList();
    });

    searchInput.addEventListener('input', (e) => {
        const searchTerm = e.target.value;
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            filterSeries(searchTerm);
        }, 300);
    });

    refreshBtn.addEventListener('click', () => {
        loadSeriesList();
    });

    // Initial load
    loadSeriesList();
});

async function loadSeriesList() {
    const loadingIndicator = document.getElementById('loadingIndicator');
    const errorMessage = document.getElementById('errorMessage');
    const seriesList = document.getElementById('seriesList');

    loadingIndicator.classList.remove('hidden');
    errorMessage.classList.add('hidden');
    seriesList.innerHTML = '';

    try {
        const headers = getAuthHeaders();
        const response = await fetch('/JellyStream/Series/List?site=' + currentSite, { headers });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error('HTTP ' + response.status + ': ' + errorText);
        }

        const data = await response.json();
        allSeries = data;
        displaySeries(allSeries);
    } catch (error) {
        console.error('Error loading series:', error);
        errorMessage.textContent = 'Error loading series: ' + error.message;
        errorMessage.classList.remove('hidden');
    } finally {
        loadingIndicator.classList.add('hidden');
    }
}

function displaySeries(seriesArray) {
    const seriesList = document.getElementById('seriesList');
    seriesList.innerHTML = '';

    if (seriesArray.length === 0) {
        seriesList.innerHTML = '<div class="loading">No series found</div>';
        return;
    }

    seriesArray.forEach(series => {
        const card = createSeriesCard(series);
        seriesList.appendChild(card);
    });
}

function createSeriesCard(series) {
    const card = document.createElement('div');
    card.className = 'series-card';
    card.dataset.seriesName = series.JellyfinName;

    const escapedName = escapeHtml(series.JellyfinName);
    const seasonText = series.SeasonCount + ' season' + (series.SeasonCount !== 1 ? 's' : '');
    const episodeText = series.EpisodeCount + ' episode' + (series.EpisodeCount !== 1 ? 's' : '');
    const statusId = 'status-' + escapedName.replace(/\s+/g, '-');

    card.innerHTML =
        '<div class="series-header">' +
            '<div>' +
                '<div class="series-name">' + escapedName + '</div>' +
                '<div class="series-info">' +
                    seasonText + ' • ' + episodeText +
                '</div>' +
            '</div>' +
            '<div class="series-actions">' +
                '<button class="btn btn-primary update-btn" onclick="updateSeries(\'' + escapedName + '\', \'' + series.Site + '\')">' +
                    'Update Series' +
                '</button>' +
            '</div>' +
        '</div>' +
        '<div class="update-status hidden" id="' + statusId + '"></div>';

    return card;
}

function filterSeries(searchTerm) {
    const filtered = allSeries.filter(series =>
        series.Name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        series.JellyfinName.toLowerCase().includes(searchTerm.toLowerCase())
    );
    displaySeries(filtered);
}

async function updateSeries(seriesName, site) {
    const statusId = 'status-' + seriesName.replace(/\s+/g, '-');
    const statusDiv = document.getElementById(statusId);
    const updateBtn = event.target;

    updateBtn.disabled = true;
    statusDiv.className = 'update-status updating';
    statusDiv.classList.remove('hidden');
    statusDiv.textContent = 'Updating series... This may take a few minutes.';

    try {
        const headers = getAuthHeaders();
        const response = await fetch('/JellyStream/Update/Series?name=' + encodeURIComponent(seriesName) + '&site=' + site, {
            method: 'POST',
            headers
        });

        if (!response.ok) {
            throw new Error(await response.text());
        }

        const result = await response.json();

        statusDiv.className = 'update-status success';
        statusDiv.textContent = '✅ Success! Updated ' + result.EpisodesUpdated + ' episodes, created ' + result.StrmFilesCreated + ' .strm files';

        setTimeout(() => {
            statusDiv.classList.add('hidden');
        }, 10000);
    } catch (error) {
        console.error('Error updating series:', error);
        statusDiv.className = 'update-status error';
        statusDiv.textContent = '❌ Error: ' + error.message;
    } finally {
        updateBtn.disabled = false;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
