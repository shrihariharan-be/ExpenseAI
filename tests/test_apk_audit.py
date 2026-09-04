import os
import json
import zipfile
import pytest

def test_api_health_endpoint(client):
    res = client.get('/api/health')
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data['status'] == 'healthy'
    assert 'ExpenseAI' in data['service']
    assert data['database'] == 'connected'

def test_release_apk_exists_and_signed():
    apk_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ExpenseAI-release.apk')
    assert os.path.exists(apk_path), f"Release APK not found at {apk_path}"
    
    size = os.path.getsize(apk_path)
    assert 5_000_000 < size < 25_000_000, f"Unexpected APK file size: {size} bytes"

    with zipfile.ZipFile(apk_path, 'r') as zf:
        namelist = zf.namelist()
        assert 'classes.dex' in namelist
        assert 'AndroidManifest.xml' in namelist
        
        # Verify V1 signatures
        sig_files = [n for n in namelist if n.startswith('META-INF/') and (n.endswith('.RSA') or n.endswith('.SF'))]
        assert len(sig_files) >= 2, f"Missing release signature files in META-INF: {sig_files}"

def test_release_apk_binary_free_of_developer_ips():
    apk_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ExpenseAI-release.apk')
    banned_patterns = [
        b'10.125.202.13',
        b'172.20.186.69',
        b'127.0.0.1',
        b'localhost',
        b'10.0.2.2',
        b':5000',
        b'192.168.'
    ]

    violations = []
    with zipfile.ZipFile(apk_path, 'r') as zf:
        for name in zf.namelist():
            data = zf.read(name)
            for pat in banned_patterns:
                if pat in data:
                    violations.append(f"{pat.decode()} in {name}")

    assert not violations, f"Banned developer endpoints found in release APK: {violations}"

def test_network_security_config_enforces_https():
    base_dir = os.path.dirname(os.path.dirname(__file__))
    nsc_path = os.path.join(base_dir, 'android-app', 'app', 'src', 'main', 'res', 'xml', 'network_security_config.xml')
    assert os.path.exists(nsc_path)

    with open(nsc_path, 'r', encoding='utf-8') as f:
        content = f.read()

    assert 'cleartextTrafficPermitted="false"' in content
    assert '<trust-anchors>' in content
