from conftest import login


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
    assert 'yandu_active_users' in body
    assert 'yandu_active_sessions' in body
    assert 'yandu_total_registered_users' in body
    assert 'yandu_user_registrations_total' in body
    assert 'yandu_visitor_funnel_events_total' in body
    assert 'yandu_anonymous_uv_rolling_1h' in body


def test_visitor_tracking_and_funnel(client):
    # 1. Anonymous visitor browsing sets yandu_vid cookie
    res = client.get('/api/v1/items/')
    assert res.status_code == 200
    assert 'yandu_vid' in res.cookies

    # 2. Unauthenticated request triggering 401
    res401 = client.get('/api/v1/users/me/overview')
    assert res401.status_code == 401

    # 3. Check metrics reflect visitor events
    metrics_res = client.get('/metrics')
    assert 'yandu_visitor_funnel_events_total{stage="browse"}' in metrics_res.text
    assert 'yandu_visitor_funnel_events_total{stage="auth_prompt_hit"}' in metrics_res.text


def test_admin_analytics_endpoints(client):
    # Login as admin
    login(client, 'admin')

    # Test user growth analytics
    res_growth = client.get('/api/v1/admin/analytics/user-growth?days=30')
    assert res_growth.status_code == 200
    growth_data = res_growth.json()
    assert 'total_users' in growth_data
    assert 'trend' in growth_data
    assert isinstance(growth_data['trend'], list)

    # Test visitor funnel analytics
    res_funnel = client.get('/api/v1/admin/analytics/visitor-funnel?days=7')
    assert res_funnel.status_code == 200
    funnel_data = res_funnel.json()
    assert 'total_unique_visitors' in funnel_data
    assert 'unregistered_browsers' in funnel_data
    assert 'funnel' in funnel_data
    assert len(funnel_data['funnel']) == 4
    assert 'friction_drop_off_pct' in funnel_data

    # Test business overview analytics
    res_biz = client.get('/api/v1/admin/analytics/business-overview')
    assert res_biz.status_code == 200
    biz_data = res_biz.json()
    assert 'liquidity' in biz_data
    assert 'ai_attribution' in biz_data
    assert 'friction' in biz_data
    assert 'dwell_insights' in biz_data
    assert 'sell_through_rate_pct' in biz_data['liquidity']
    assert 'first_inquiry_rate_72h_pct' in biz_data['liquidity']
    assert 'zombie_rate_pct' in biz_data['liquidity']
    assert 'total_gmv_yuan' in biz_data['liquidity']
    assert 'avg_order_value_yuan' in biz_data['liquidity']
    assert 'recent_30d_gmv_yuan' in biz_data['liquidity']
    assert 'push_to_chat_cvr_pct' in biz_data['ai_attribution']
    assert 'draft_abandonment_pct' in biz_data['friction']
    assert 'page_distribution' in biz_data['dwell_insights']
    assert 'hesitation_items' in biz_data['dwell_insights']


def test_dwell_time_tracking_and_advanced_metrics(client):
    # 1. Post a page dwell report
    dwell_payload = {
        'page': 'item_detail',
        'duration_seconds': 45
    }
    res = client.post('/api/v1/analytics/dwell', json=dwell_payload)
    assert res.status_code == 200
    assert res.json() == {'ok': True}

    # 2. Check Prometheus metrics for new gauges
    metrics_res = client.get('/metrics')
    assert metrics_res.status_code == 200
    body = metrics_res.text
    assert 'yandu_first_inquiry_rate_72h_pct' in body
    assert 'yandu_zombie_listing_rate_pct' in body
    assert 'yandu_page_dwell_seconds_total' in body
