const markers = { pickup: null, destination: null };
let map = null;
let mapTarget = 'pickup';
let mapUnavailable = false;

function setMapTarget(kind) {
  mapTarget = kind;
  document.querySelectorAll('[data-map-target]').forEach((button) => {
    button.classList.toggle('active', button.dataset.mapTarget === kind);
  });
  document.getElementById('mapTargetHint').textContent = mapUnavailable
    ? 'Map preview did not load. Search for a place above and tap a result to select it.'
    : `Click the map to set your ${kind}. You can move the pin by clicking again.`;
}

function updateFormState() {
  const hasPickup = Boolean(document.getElementById('pickup_latitude').value);
  const hasDestination = Boolean(document.getElementById('destination_latitude').value);
  document.getElementById('submitRide').disabled = !(hasPickup && hasDestination);
  if (!hasPickup) setMapTarget('pickup');
  else if (!hasDestination) setMapTarget('destination');
  document.getElementById('mapHint').textContent = hasPickup && hasDestination
    ? 'Both locations are set. Check the pins, time and sharing preference.'
    : hasPickup
      ? 'Pickup is set. Now choose your destination.'
      : hasDestination
        ? 'Destination is set. Now choose your pickup.'
        : 'Choose your pickup and destination to continue.';
}

function setPoint(kind, lat, lng, label) {
  lat = Number(lat);
  lng = Number(lng);
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
  if (markers[kind] && map) map.removeLayer(markers[kind]);
  markers[kind] = null;
  if (map && window.L) {
    const color = kind === 'pickup' ? '#087f5b' : '#d2691e';
    markers[kind] = L.circleMarker([lat, lng], {
      radius: 10, color, fillColor: color, fillOpacity: 0.9, weight: 3,
    }).addTo(map).bindPopup(`${kind === 'pickup' ? 'Pickup' : 'Destination'}: ${label}`).openPopup();
  }
  document.getElementById(`${kind}_latitude`).value = lat;
  document.getElementById(`${kind}_longitude`).value = lng;
  document.getElementById(`${kind}_name`).value = label;
  document.getElementById(`${kind}_selected`).textContent = `${kind === 'pickup' ? 'Pickup' : 'Destination'} selected: ${label}`;
  updateFormState();
}

function clearPoint(kind) {
  if (markers[kind] && map) map.removeLayer(markers[kind]);
  markers[kind] = null;
  document.getElementById(`${kind}_latitude`).value = '';
  document.getElementById(`${kind}_longitude`).value = '';
  document.getElementById(`${kind}_selected`).textContent = `${kind === 'pickup' ? 'Pickup' : 'Destination'} not selected yet`;
  updateFormState();
}

async function reverseGeocode(lat, lng) {
  const url = new URL('https://nominatim.openstreetmap.org/reverse');
  url.search = new URLSearchParams({ format: 'jsonv2', lat, lon: lng });
  const response = await fetch(url, { headers: { 'Accept-Language': 'en' } });
  if (!response.ok) throw new Error('Could not look up this map point.');
  const data = await response.json();
  return data.display_name || `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
}

function initializeMap() {
  if (!window.L || map) return Boolean(map);
  map = L.map('map').setView([23.8103, 90.4125], 12);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors',
  }).addTo(map);
  map.on('click', async (event) => {
    const kind = mapTarget;
    const hint = document.getElementById('mapHint');
    hint.textContent = 'Finding the name of this map point...';
    let label = `${event.latlng.lat.toFixed(5)}, ${event.latlng.lng.toFixed(5)}`;
    try {
      label = await reverseGeocode(event.latlng.lat, event.latlng.lng);
    } catch (error) { /* Keep the coordinates as a valid location fallback. */ }
    setPoint(kind, event.latlng.lat, event.latlng.lng, label);
  });

  // Restore pins if a user picked search results before the fallback map loaded.
  ['pickup', 'destination'].forEach((kind) => {
    const lat = document.getElementById(`${kind}_latitude`).value;
    const lng = document.getElementById(`${kind}_longitude`).value;
    if (lat && lng) setPoint(kind, lat, lng, document.getElementById(`${kind}_name`).value);
  });
  setMapTarget(mapTarget);
  return true;
}

function loadFallbackLeaflet() {
  return new Promise((resolve) => {
    const css = document.createElement('link');
    css.rel = 'stylesheet';
    css.href = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css';
    document.head.append(css);
    const script = document.createElement('script');
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js';
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.head.append(script);
  });
}

async function startMap() {
  if (!window.L) await loadFallbackLeaflet();
  if (!initializeMap()) {
    mapUnavailable = true;
    setMapTarget(mapTarget);
  }
}

document.querySelectorAll('[data-map-target]').forEach((button) => {
  button.addEventListener('click', () => setMapTarget(button.dataset.mapTarget));
});

document.querySelectorAll('[data-search]').forEach((button) => {
  button.addEventListener('click', async () => {
    const kind = button.dataset.search;
    const query = document.getElementById(`${kind}_name`).value.trim();
    const results = document.getElementById(`${kind}_results`);
    if (!query) {
      results.textContent = 'Type a place name first.';
      return;
    }

    button.disabled = true;
    results.textContent = 'Searching in Bangladesh...';
    try {
      const url = new URL('https://nominatim.openstreetmap.org/search');
      url.search = new URLSearchParams({
        format: 'jsonv2', limit: '5', countrycodes: 'bd', q: query,
      });
      const response = await fetch(url, { headers: { 'Accept-Language': 'en' } });
      if (!response.ok) throw new Error('Location search is temporarily unavailable.');
      const places = await response.json();
      results.replaceChildren();
      if (!places.length) {
        results.textContent = 'No result found. Try a nearby landmark or choose directly on the map.';
        return;
      }
      const title = document.createElement('p');
      title.className = 'results-title';
      title.textContent = 'Tap the correct address below to select it:';
      results.append(title);
      places.forEach((place) => {
        const option = document.createElement('button');
        option.type = 'button';
        option.className = 'location-result';
        option.textContent = place.display_name;
        option.addEventListener('click', () => {
          const lat = Number(place.lat);
          const lng = Number(place.lon);
          setPoint(kind, lat, lng, place.display_name);
          if (map) map.setView([lat, lng], 16);
          results.replaceChildren();
        });
        results.append(option);
      });
    } catch (error) {
      results.textContent = error.message || 'Search failed. Choose the location directly on the map.';
    } finally {
      button.disabled = false;
    }
  });
});

document.querySelectorAll('[data-use-location]').forEach((button) => {
  button.addEventListener('click', () => {
    const kind = button.dataset.useLocation;
    const hint = document.getElementById('mapHint');
    if (!navigator.geolocation) {
      hint.textContent = 'Location access is unavailable. Search for a place or click the map.';
      return;
    }
    button.disabled = true;
    hint.textContent = 'Getting your current location...';
    navigator.geolocation.getCurrentPosition(async ({ coords }) => {
      let label = `${coords.latitude.toFixed(5)}, ${coords.longitude.toFixed(5)}`;
      try { label = await reverseGeocode(coords.latitude, coords.longitude); }
      catch (error) { /* Coordinates still identify a valid point. */ }
      setPoint(kind, coords.latitude, coords.longitude, label);
      if (map) map.setView([coords.latitude, coords.longitude], 16);
      button.disabled = false;
    }, (error) => {
      const messages = {
        1: 'Location permission was not allowed. Search or choose on the map instead.',
        2: 'Your location could not be found. Search or choose on the map instead.',
        3: 'Location lookup took too long. Try again or choose on the map.',
      };
      hint.textContent = messages[error.code] || 'Could not get your location. Search or choose on the map.';
      button.disabled = false;
    }, { enableHighAccuracy: false, timeout: 12000, maximumAge: 60000 });
  });
});

['pickup', 'destination'].forEach((kind) => {
  const input = document.getElementById(`${kind}_name`);
  input.addEventListener('input', () => {
    clearPoint(kind);
    document.getElementById(`${kind}_results`).replaceChildren();
  });
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      document.querySelector(`[data-search="${kind}"]`).click();
    }
  });
});

startMap();
