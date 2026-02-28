// This script runs on every Nexus Mods mod page
// cache for mod data. only works for navigating between tabs on same mod page
let downloadCache = {
  data: null,
  timestamp: null,
  expiresIn: 60000
};

// cache for api mod status
let apiModCache = {
  trackedMods: null,
  endorsedMods: null,
  timestamp: null,
  expiresIn: 60000,
  game: null
};

const TRACKED_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16"><path d="M9.828.722a.5.5 0 0 1 .354.146l4.95 4.95a.5.5 0 0 1 0 .707c-.48.48-1.072.588-1.503.588-.177 0-.335-.018-.46-.039l-3.134 3.134a6 6 0 0 1 .16 1.013c.046.702-.032 1.687-.72 2.375a.5.5 0 0 1-.707 0l-2.829-2.828-3.182 3.182c-.195.195-1.219.902-1.414.707s.512-1.22.707-1.414l3.182-3.182-2.828-2.829a.5.5 0 0 1 0-.707c.688-.688 1.673-.767 2.375-.72a6 6 0 0 1 1.013.16l3.134-3.133a3 3 0 0 1-.04-.461c0-.43.108-1.022.589-1.503a.5.5 0 0 1 .353-.146"/></svg>';

const ENDORSED_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16"><path d="M6.956 1.745C7.021.81 7.908.087 8.864.325l.261.066c.463.116.874.456 1.012.965.22.816.533 2.511.062 4.51a10 10 0 0 1 .443-.051c.713-.065 1.669-.072 2.516.21.518.173.994.681 1.2 1.273.184.532.16 1.162-.234 1.733q.086.18.138.363c.077.27.113.567.113.856s-.036.586-.113.856c-.039.135-.09.273-.16.404.169.387.107.819-.003 1.148a3.2 3.2 0 0 1-.488.901c.054.152.076.312.076.465 0 .305-.089.625-.253.912C13.1 15.522 12.437 16 11.5 16H8c-.605 0-1.07-.081-1.466-.218a4.8 4.8 0 0 1-.97-.484l-.048-.03c-.504-.307-.999-.609-2.068-.722C2.682 14.464 2 13.846 2 13V9c0-.85.685-1.432 1.357-1.615.849-.232 1.574-.787 2.132-1.41.56-.627.914-1.28 1.039-1.639.199-.575.356-1.539.428-2.59z"/></svg>';

function createApiStatusIcon(type, svgMarkup, title) {
  const icon = document.createElement('span');
  icon.className = `api-status-icon ${type}-icon`;
  icon.innerHTML = svgMarkup;
  icon.title = title;
  return icon;
}

async function getApiKey() {
  const result = await chrome.storage.local.get(['nexusApiKey']);
  return result.nexusApiKey;
}

function getCurrentGame() {
  const urlMatch = window.location.pathname.match(/\/([^\/]+)\/mods\/(\d+)/);
  if (urlMatch) {
    return urlMatch[1];
  }
  return null;
}

async function fetchTrackedMods(apiKey) {
  const trackedResponse = await fetch('https://api.nexusmods.com/v1/user/tracked_mods.json', {
    headers: {
      'apikey': apiKey
    }
  });

  if (!trackedResponse.ok) {
    console.error('Tracked mods API error:', trackedResponse.status);
    return [];
  }

  const trackedMods = await trackedResponse.json();
  return trackedMods;
}

async function fetchEndorsedMods(apiKey) {
  const endorsedResponse = await fetch('https://api.nexusmods.com/v1/user/endorsements.json', {
    headers: {
      'apikey': apiKey
    }
  });

  if (!endorsedResponse.ok) {
    console.error('Endorsed mods API error:', endorsedResponse.status);
    return [];
  }
  
  const endorsedMods = await endorsedResponse.json();
  return endorsedMods;
}

function isCacheAlive(cache, currentGame, now, maxAgeMs) {
  return (
    cache &&
    cache.trackedMods &&
    cache.endorsedMods &&
    cache.timestamp &&
    cache.game === currentGame &&
    now - cache.timestamp < maxAgeMs
  );
}

async function fetchNexusData(apiKey, currentGame) {
  const now = Date.now();
  try {
    if (isCacheAlive(apiModCache, currentGame, now, apiModCache.expiresIn)) {
      return {
        trackedMods: apiModCache.trackedMods,
        endorsedMods: apiModCache.endorsedMods
      };
    }

    const stored = await chrome.storage.local.get('apiModCache');
    const storedCache = stored.apiModCache;
    if (isCacheAlive(storedCache, currentGame, now, apiModCache.expiresIn)) {
      apiModCache.trackedMods = storedCache.trackedMods;
      apiModCache.endorsedMods = storedCache.endorsedMods;
      apiModCache.timestamp = storedCache.timestamp;
      apiModCache.game = storedCache.game;

      return {
        trackedMods: apiModCache.trackedMods,
        endorsedMods: apiModCache.endorsedMods
      };
    }

    const trackedMods = await fetchTrackedMods(apiKey)
    const endorsedMods = await fetchEndorsedMods(apiKey)

    // filter to only include mods from the current game
    const gameTracked = trackedMods.filter(mod => mod.domain_name === currentGame);
    const gameEndorsed = endorsedMods.filter(mod => mod.domain_name === currentGame);

    apiModCache.trackedMods = gameTracked;
    apiModCache.endorsedMods = gameEndorsed;
    apiModCache.timestamp = now;
    apiModCache.game = currentGame;

    try {
      await chrome.storage.local.set({
        apiModCache: {
          trackedMods: gameTracked,
          endorsedMods: gameEndorsed,
          timestamp: now,
          game: currentGame
        }
      });
    } catch (storageError) {
      console.error('Error writing API mod cache to storage:', storageError);
    }

    return {
      trackedMods: gameTracked,
      endorsedMods: gameEndorsed
    };
  } catch (error) {
    console.error('Error fetching API mod status:', error);
    return { trackedMods: [], endorsedMods: [] };
  }
}

async function fetchMo2Data() {
  const now = Date.now();
  try {

    if (
      downloadCache.data &&
      downloadCache.timestamp &&
      now - downloadCache.timestamp < downloadCache.expiresIn
    ) {
      return downloadCache.data;
    }

    const stored = await chrome.storage.local.get('mo2Cache');
    const storedCache = stored.mo2Cache;
    if (storedCache && storedCache.timestamp && now - storedCache.timestamp < downloadCache.expiresIn) {
      const enabledModIds = new Set(storedCache.enabledModIds || []);
      const allModIds = new Set(storedCache.allModIds || []);
      const data = { enabledModIds, allModIds };
      downloadCache.data = data;
      downloadCache.timestamp = storedCache.timestamp;
      return data;
    }

    const enabledResponse = await fetch('http://localhost:52526/api/mod-ids/enabled');
    const enabledModsJson = await enabledResponse.json();
    const enabledModIds = new Set(enabledModsJson.enabled_ids);

    const allResponse = await fetch('http://localhost:52526/api/mod-ids');
    const allModsJson = await allResponse.json();
    const allModIds = new Set(allModsJson.nexus_ids);

    downloadCache.data = { enabledModIds, allModIds };
    downloadCache.timestamp = now;

    try {
      await chrome.storage.local.set({
        mo2Cache: {
          enabledModIds: Array.from(enabledModIds),
          allModIds: Array.from(allModIds),
          timestamp: now
        }
      });
    } catch (storageError) {
      console.error('Error writing MO2 cache to storage:', storageError);
    }

    return { enabledModIds, allModIds };
  } catch (error) {
    console.error('Error fetching user mods:', error);
    return { enabledModIds: new Set(), allModIds: new Set() };
  }
}

async function main() {
  const requirementRows = document.querySelectorAll('table tbody tr');
  if (requirementRows.length === 0) {
    console.error('No requirement rows found');
    return;
  }

  const defaults = { showEnabled: true, showInstalled: true, showUninstalled: true, showTracked: false, showEndorsed: false };
  const [userMods, apiKey, settings] = await Promise.all([
    fetchMo2Data(),
    getApiKey(),
    chrome.storage.local.get(defaults)
  ]);
  const { showEnabled, showInstalled, showUninstalled, showTracked, showEndorsed } = { ...defaults, ...settings };

  if (!userMods) {
    console.error('Could not fetch user mods');
    return;
  }

  const { enabledModIds, allModIds } = userMods;
  const hasMO2Data = enabledModIds.size > 0 || allModIds.size > 0;

  const currentGame = getCurrentGame();
  let apiModStatus = { trackedMods: [], endorsedMods: [] };
  if (apiKey && currentGame) {
    apiModStatus = await fetchNexusData(apiKey, currentGame);
  }

  const trackedModIds = new Set(apiModStatus.trackedMods.map(mod => mod.mod_id));
  const endorsedModIds = new Set(apiModStatus.endorsedMods.map(mod => mod.mod_id));

  const hasNexusData = apiKey && (trackedModIds.size > 0 || endorsedModIds.size > 0);
  if (!hasMO2Data && !hasNexusData) {
    console.error('No mod data: MO2 unreachable and no Nexus data to show');
    return;
  }

  for (const row of requirementRows) {
    // skip if we've already processed this row
    if (row.querySelector('.enabled-status')) continue;

    const nameCell = row.querySelector('td:first-child');
    if (!nameCell) continue;

    // try to extract mod ID from the link if available
    const modLink = nameCell.querySelector('a');
    let modId = null;
    if (modLink) {
      const linkMatch = modLink.href.match(/\/mods\/(\d+)/);
      // [1] corresponds to mod id in url 
      // specify base 10 to avoid errors with leading 0 strings
      if (linkMatch) modId = parseInt(linkMatch[1], 10);
    }
    if (modId == null) continue; 
      }
    }

    chrome.storage.local.get({ showEnabled: true, showInstalled: true, showTracked: true, showEndorsed: true }, async (settings) => {
      const isEnabled = enabledModIds.has(modId);
      const isInstalled = allModIds.has(modId);
      const isTracked = trackedModIds.has(modId);
      const isEndorsed = endorsedModIds.has(modId);
      const showNexusBadges = apiKey && ((settings.showTracked && isTracked) || (settings.showEndorsed && isEndorsed));

      const statusCell = row.querySelector('td:last-child');
      if (statusCell) {
        const indicator = document.createElement('div');
        let shouldShow = false;

        if (hasMO2Data) {
          if (isEnabled && settings.showEnabled) {
            indicator.className = 'enabled-status enabled';
            indicator.innerHTML = '<span class="status-icon">✓</span> Enabled';
            shouldShow = true;
          } else if (isInstalled) {
            indicator.className = 'enabled-status installed';
            indicator.innerHTML = '<span class="status-icon">✓</span> Installed';
            shouldShow = true;
          } else {
            indicator.className = 'enabled-status not-installed';
            indicator.innerHTML = '<span class="status-icon">✗</span> Not Installed';
            shouldShow = true;
          }
        } else if (showNexusBadges) {
          indicator.className = 'enabled-status unknown';
          indicator.innerHTML = '<span class="status-icon">?</span> Unknown';
          shouldShow = true;
        }

        if (shouldShow) {
          statusCell.classList.add('mod-status-cell');
          
          if (apiKey && settings.showTracked && isTracked) {
            const trackedIcon = createApiStatusIcon('tracked', TRACKED_SVG, 'Tracked');
            indicator.appendChild(trackedIcon);
          }

          if (apiKey && settings.showEndorsed && isEndorsed) {
            const endorsedIcon = createApiStatusIcon('endorsed', ENDORSED_SVG, 'Endorsed');
            indicator.appendChild(endorsedIcon);
          }
          
          statusCell.appendChild(indicator);
        }
      }
    });
  });
}

// run script on page load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', main);
} else {
  main();
}

// rerun script when changing pages
let lastUrl = location.href;
new MutationObserver(() => {
  const url = location.href;
  if (url !== lastUrl) {
    lastUrl = url;
    setTimeout(main, 1000);
  }
}).observe(document, { subtree: true, childList: true });

// clear rows if setting changes
chrome.storage.onChanged.addListener((changes, namespace) => {
  if (namespace === 'local' && (changes.showEnabled || changes.showInstalled || changes.showUninstalled || changes.showTracked || changes.showEndorsed || changes.nexusApiKey)) {
    document.querySelectorAll('.enabled-status').forEach(el => el.remove());
    document.querySelectorAll('.mod-status-cell').forEach(el => el.classList.remove('mod-status-cell'));
    // clear api cache if key changes
    if (changes.nexusApiKey) {
      apiModCache.trackedMods = null;
      apiModCache.endorsedMods = null;
      apiModCache.timestamp = null;
      apiModCache.game = null;
      chrome.storage.local.remove('apiModCache');
    }
    main();
  }
});