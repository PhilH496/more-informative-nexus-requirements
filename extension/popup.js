document.addEventListener('DOMContentLoaded', async () => {
  const defaults = {
    showEnabled: true,
    showUninstalled: true,
    showTracked: false,
    showEndorsed: false,
    useNexusApi: false
  };

  const result = await chrome.storage.local.get(defaults);

  const enabledCheckbox = document.querySelector('#enabled-mods-container input');
  const uninstalledCheckbox = document.getElementById('uninstalledCheckbox');
  const useNexusApiCheckbox = document.getElementById('useNexusApiCheckbox');
  const trackedCheckbox = document.getElementById('trackedCheckbox');
  const endorsedCheckbox = document.getElementById('endorsedCheckbox');
  const apiKeyInput = document.getElementById('apiKey');

  const apiKeyResult = await chrome.storage.local.get(['nexusApiKey']);
  if (apiKeyResult.nexusApiKey) {
    apiKeyInput.value = apiKeyResult.nexusApiKey;
  }

  function updateToggleStates() {
    const useNexusApi = useNexusApiCheckbox.checked;
    apiKeyInput.disabled = !useNexusApi;
    const hasApiKey = apiKeyInput.value.trim().length > 0;
    const canShowTrackedEndorsed = !useNexusApi || hasApiKey;
    trackedCheckbox.disabled = !canShowTrackedEndorsed;
    endorsedCheckbox.disabled = !canShowTrackedEndorsed;
  }

  if (useNexusApiCheckbox) {
    useNexusApiCheckbox.checked = result.useNexusApi;
    useNexusApiCheckbox.addEventListener('change', (e) => {
      const useNexusApi = e.target.checked;
      chrome.storage.local.set({ useNexusApi });
      updateToggleStates();
    });
  }

  updateToggleStates();

  // update api key when changed
  apiKeyInput.addEventListener('input', () => {
    const apiKey = apiKeyInput.value.trim();
    chrome.storage.local.set({ nexusApiKey: apiKey });
    updateToggleStates();
  });

  if (enabledCheckbox) {
    enabledCheckbox.checked = result.showEnabled;
    enabledCheckbox.addEventListener('change', (e) => {
      chrome.storage.local.set({ showEnabled: e.target.checked });
    });
  }

  if (uninstalledCheckbox) {
    uninstalledCheckbox.checked = result.showUninstalled;
    uninstalledCheckbox.addEventListener('change', (e) => {
      chrome.storage.local.set({ showUninstalled: e.target.checked });
    });
  }

  if (trackedCheckbox) {
    trackedCheckbox.checked = result.showTracked;
    trackedCheckbox.addEventListener('change', (e) => {
      chrome.storage.local.set({ showTracked: e.target.checked });
    });
  }

  if (endorsedCheckbox) {
    endorsedCheckbox.checked = result.showEndorsed;
    endorsedCheckbox.addEventListener('change', (e) => {
      chrome.storage.local.set({ showEndorsed: e.target.checked });
    });
  }
});
