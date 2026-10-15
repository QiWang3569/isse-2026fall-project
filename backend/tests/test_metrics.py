def test_prometheus_metrics_endpoint(client):
    # Trigger an API request
    res = client.get('/api/v1/health')
    assert res.status_code == 200

    # Scrape metrics endpoint
    metrics_res = client.get('/metrics')
    assert metrics_res.status_code == 200
    assert 'text/plain' in metrics_res.headers.get('content-type', '')
    body = metrics_res.text
    assert 'http_requests_total' in body
    assert 'http_request_duration_seconds' in body
