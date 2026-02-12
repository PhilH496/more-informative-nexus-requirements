document.addEventListener('DOMContentLoaded', async () => {
  const defaults = {
    showEnabled: true
  };

  const result = await chrome.storage.local.get(defaults);

  const enabledCheckbox = document.querySelector('#enabled-mods-container input');

  if (enabledCheckbox) {
    enabledCheckbox.checked = result.showEnabled;
    enabledCheckbox.addEventListener('change', (e) => {
      chrome.storage.local.set({ showEnabled: e.target.checked });
    });
  }
});
