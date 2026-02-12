async function fetchUserMods() {
  const now = Date.now();
  if (downloadCache.data && downloadCache.timestamp && (now - downloadCache.timestamp < downloadCache.expiresIn)) {
    return downloadCache.data;
  }

  try {
    const enabledResponse = await fetch('http://localhost:52526/api/mod-ids/enabled');
    const enabledModsJson = await enabledResponse.json();
    const enabledModIds = new Set(enabledModsJson.enabled_ids);

    const allResponse = await fetch('http://localhost:52526/api/mod-ids');
    const allModsJson = await allResponse.json();
    const allModIds = new Set(allModsJson.nexus_ids);

    downloadCache.data = { enabledModIds, allModIds };
    downloadCache.timestamp = now;

    return { enabledModIds, allModIds };
  } catch (error) {
    console.error('Error fetching user mods:', error);
    return { enabledModIds: new Set(), allModIds: new Set() };
  }
}

async function addEnabledIndicators() {
  const requirementRows = document.querySelectorAll('table tbody tr');

  if (requirementRows.length === 0) {
    console.log('No requirement rows found');
    return;
  }

  const userMods = await fetchUserMods();
  if (!userMods) {
    console.log('Could not fetch user mods');
    return;
  }
  const { enabledModIds, allModIds } = userMods;

  if (enabledModIds.size === 0) {
    console.log('No enabled mods found');
    return;
  } else if (allModIds.size === 0) {
    console.log('No installed mods found');
    return;
  }

  requirementRows.forEach(row => {
    // skip if we've already processed this row
    if (row.querySelector('.enabled-status')) {
      return;
    }

    // get mod name from the first cell
    const nameCell = row.querySelector('td:first-child');
    if (!nameCell) return;

    const modLink = nameCell.querySelector('a');

    // try to extract mod ID from the link if available
    let modId = null;
    if (modLink) {
      const linkMatch = modLink.href.match(/\/mods\/(\d+)/);
      if (linkMatch) {
        modId = parseInt(linkMatch[1], 10);
      }
    }

    chrome.storage.local.get({ showEnabled: true, showInstalled: true }, (settings) => {
      const enabledStatus = enabledModIds.has(modId);
      const installedMods = allModIds.has(modId);

      const statusCell = row.querySelector('td:last-child');
      if (statusCell) {
        const indicator = document.createElement('div');
        let shouldShow = false;

        if (enabledStatus === true && settings.showEnabled) {
          indicator.className = 'enabled-status enabled';
          indicator.innerHTML = '<span class="status-icon">✓</span> Enabled';
          shouldShow = true;
        } else if (installedMods === true) { // no setting for this. kinda the whole point
          indicator.className = 'enabled-status installed';
          indicator.innerHTML = '<span class="status-icon">✓</span> Installed';
          shouldShow = true;
        } else {
          indicator.className = 'enabled-status not-installed';
          indicator.innerHTML = '<span class="status-icon">?</span> Not Installed';
          shouldShow = true;
        }

        if (shouldShow) {
          statusCell.classList.add('mod-status-cell');
          statusCell.appendChild(indicator);
        }
      }
    });
  });