import requests

def test_status():
    url = 'http://localhost:52526/api/status'
    response = requests.get(url)
    assert response.status_code == 200
    assert response.text == '{"status": "ok"}'
    print('Status test passed')
def test_mod_ids():
    url = 'http://localhost:52526/api/mod-ids'
    response = requests.get(url)
    assert response.status_code == 200
    assert response.json()['nexus_ids'] is not None
    assert len(response.json()['nexus_ids']) > 0
    print('Mod IDs test passed')

# TODO: Add tests for other API endpoints
# GET  /api/mod-ids/downloaded    - Returns all downloaded Nexus mod IDs
# GET  /api/mod-ids/enabled       - Returns all enabled Nexus mod IDs
# GET  /api/mod-ids/tracked       - Returns all tracked Nexus mod IDs
# GET  /api/mod-ids/endorsements  - Returns all endorsed Nexus mod IDs
if __name__ == '__main__':
    test_status()
    test_mod_ids()